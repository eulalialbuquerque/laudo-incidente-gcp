"""
controle: uma réplica do serviço que checa cotas (papel do Service Control).

Ao subir, carrega a política do banco de políticas e só então passa a
responder /checar com 200. Depois recarrega a política a cada RECARGA_S
segundos, que é como a política nova "se espalha" para todas as réplicas
(no Google, a replicação global levou segundos).

O defeito do incidente está em aplicar(): sem validação, um campo em branco
(None) quebra o int() e derruba o processo, do mesmo jeito que o ponteiro nulo
derrubou o Service Control. Quem reinicia o processo é o supervisor.py.

Variáveis que mudam o comportamento:
  BACKOFF=sem_backoff  nova tentativa de carga após INTERVALO_FIXO_S (0,1 s)
  BACKOFF=jitter       backoff exponencial com jitter total: espera aleatória
                       entre 0 e min(TETO_S, BASE_S * 2^tentativa)
  VALIDAR=1            política inválida é recusada e a anterior é mantida
"""

import json
import os
import random
import socket
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from comum import LogCSV, env_float, env_int

REPLICA = os.getenv("REPLICA") or socket.gethostname()
POLITICAS_URL = os.getenv("POLITICAS_URL", "http://politicas:8000")
BACKOFF = os.getenv("BACKOFF", "sem_backoff")
VALIDAR = os.getenv("VALIDAR", "0") == "1"
TIMEOUT_S = env_float("TIMEOUT_S", 1.0)
RECARGA_S = env_float("RECARGA_S", 5.0)
INTERVALO_FIXO_S = env_float("INTERVALO_FIXO_S", 0.1)
BASE_S = env_float("BASE_S", 0.5)
TETO_S = env_float("TETO_S", 10.0)
PORTA = env_int("PORTA", 8080)

log = LogCSV(f"controle_{REPLICA}.csv", ["replica", "pid", "evento", "detalhe"])
estado = {"limite": None, "versao": None}


def registrar(evento, detalhe=""):
    log.escrever(REPLICA, os.getpid(), evento, detalhe)


def espera_antes_de_tentar_de_novo(tentativa):
    if BACKOFF == "jitter":
        return random.uniform(0, min(TETO_S, BASE_S * 2 ** tentativa))
    return INTERVALO_FIXO_S


def buscar_politica():
    with urllib.request.urlopen(POLITICAS_URL + "/politica", timeout=TIMEOUT_S) as resposta:
        return json.loads(resposta.read())


def politica_valida(politica):
    limite = politica.get("limite_por_minuto")
    return isinstance(limite, int) and not isinstance(limite, bool) and limite > 0


def aplicar(politica):
    """True se aplicou. Sem VALIDAR, um campo em branco levanta TypeError aqui."""
    if VALIDAR and not politica_valida(politica):
        registrar("politica_recusada", f"versao={politica.get('versao')}")
        return False
    limite = int(politica["limite_por_minuto"])  # None -> TypeError: o "ponteiro nulo"
    estado["limite"] = limite
    estado["versao"] = politica.get("versao")
    return True


def carregar_ao_subir():
    tentativa = 0
    while True:
        inicio = time.monotonic()
        try:
            politica = buscar_politica()
        except Exception as erro:  # timeout, 503, conexão recusada
            espera = espera_antes_de_tentar_de_novo(tentativa)
            registrar(
                "carga_falhou",
                f"{type(erro).__name__} apos {(time.monotonic() - inicio) * 1000:.0f} ms; "
                f"nova tentativa em {espera:.2f} s",
            )
            time.sleep(espera)
            tentativa += 1
            continue
        if aplicar(politica):
            registrar("politica_carregada", f"versao={estado['versao']} tentativas={tentativa + 1}")
            return
        # Política recusada e nenhuma anterior: espera e tenta de novo.
        time.sleep(espera_antes_de_tentar_de_novo(tentativa))
        tentativa += 1


def recarregar_para_sempre():
    while True:
        time.sleep(RECARGA_S)
        try:
            politica = buscar_politica()
        except Exception as erro:
            # Já tem uma política válida: segue com ela e tenta no próximo ciclo.
            registrar("recarga_falhou", type(erro).__name__)
            continue
        if politica.get("versao") != estado["versao"]:
            if aplicar(politica):
                registrar("politica_atualizada", f"versao={estado['versao']}")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path != "/checar":
            status, corpo = 404, {"erro": "rota inexistente"}
        elif estado["limite"] is None:
            status, corpo = 503, {"erro": "sem politica carregada"}
        else:
            status, corpo = 200, {"replica": REPLICA, "limite_por_minuto": estado["limite"]}
        dados = json.dumps(corpo).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


def main():
    servidor = Servidor(("0.0.0.0", PORTA), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    registrar("processo_iniciado", f"backoff={BACKOFF} validar={int(VALIDAR)}")
    carregar_ao_subir()
    recarregar_para_sempre()


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        registrar("crash", repr(erro))
        raise SystemExit(1)
