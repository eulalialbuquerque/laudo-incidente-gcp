"""
supervisor: reinicia o processo controle.py quando ele cai (papel do
orquestrador que reiniciava as tarefas do Service Control).

Fica dentro do container para que o reinício seja controlado e medido por nós,
e não pelo atraso crescente que o Docker aplica sozinho no restart: always.

  BACKOFF=sem_backoff  reinicia após REINICIO_FIXO_S (1 s): todas as réplicas
                       que caíram juntas voltam juntas
  BACKOFF=jitter       reinicia após um tempo aleatório entre 0 e
                       min(TETO_S, BASE_S * 2^quedas_seguidas)

A primeira subida espera um tempo aleatório até ATRASO_INICIAL_S para que as
réplicas não comecem todas no mesmo instante (implantação gradual, como em
qualquer ambiente real). Isso vale nos dois modos.
"""

import os
import random
import signal
import socket
import subprocess
import sys
import time

from comum import LogCSV, env_float

REPLICA = os.getenv("REPLICA") or socket.gethostname()
BACKOFF = os.getenv("BACKOFF", "sem_backoff")
REINICIO_FIXO_S = env_float("REINICIO_FIXO_S", 1.0)
BASE_S = env_float("BASE_S", 0.5)
TETO_S = env_float("TETO_S", 10.0)
ATRASO_INICIAL_S = env_float("ATRASO_INICIAL_S", 10.0)
# Se o processo ficou de pé pelo menos isso, a contagem de quedas zera.
ESTAVEL_APOS_S = env_float("ESTAVEL_APOS_S", 10.0)

log = LogCSV(f"controle_{REPLICA}.csv", ["replica", "pid", "evento", "detalhe"])
filho = None


def encerrar(*_):
    if filho and filho.poll() is None:
        filho.terminate()
    sys.exit(0)


def main():
    global filho
    signal.signal(signal.SIGTERM, encerrar)
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "controle.py")
    quedas_seguidas = 0
    primeira = True
    while True:
        if primeira:
            atraso = random.uniform(0, ATRASO_INICIAL_S)
        elif BACKOFF == "jitter":
            atraso = random.uniform(0, min(TETO_S, BASE_S * 2 ** quedas_seguidas))
        else:
            atraso = REINICIO_FIXO_S
        log.escrever(REPLICA, os.getpid(), "supervisor_aguardando", f"{atraso:.2f}")
        time.sleep(atraso)

        inicio = time.monotonic()
        filho = subprocess.Popen([sys.executable, caminho])
        codigo = filho.wait()
        duracao = time.monotonic() - inicio
        log.escrever(
            REPLICA, os.getpid(), "processo_encerrado", f"codigo={codigo} duracao_s={duracao:.2f}"
        )
        quedas_seguidas = 0 if duracao >= ESTAVEL_APOS_S else quedas_seguidas + 1
        primeira = False


if __name__ == "__main__":
    main()
