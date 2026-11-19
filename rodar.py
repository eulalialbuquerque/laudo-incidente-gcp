"""
Roda uma execução completa da miniatura e analisa os logs.

    python rodar.py --cenario sem_backoff --rodada 1
    python rodar.py --cenario jitter      --rodada 1
    python rodar.py --cenario validacao   --rodada 1

Cenários:
  sem_backoff  comportamento do incidente: reinício e nova tentativa em
               intervalo fixo, sem validação da política
  jitter       mitigação: backoff exponencial com jitter no reinício e nas
               novas tentativas (o resto igual)
  validacao    mitigação alternativa: política inválida é recusada e a
               anterior é mantida (sem backoff)

Cada execução grava em logs/<cenario>_r<rodada>/: os CSV brutos de cada
container, o log do docker compose, os parâmetros e o resumo da análise.
Só precisa de Python 3.8+ e Docker (com Compose v2) no host.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PROJETO = "miniatura-gcp"

CENARIOS = {
    "sem_backoff": {"BACKOFF": "sem_backoff", "VALIDAR": "0"},
    "jitter": {"BACKOFF": "jitter", "VALIDAR": "0"},
    "validacao": {"BACKOFF": "sem_backoff", "VALIDAR": "1"},
}

PADROES = {
    "REPLICAS": "30",
    "CAPACIDADE": "1",
    "CUSTO_MS": "100",
    "FILA_MAX": "100",
    "TIMEOUT_S": "1.0",
    "RECARGA_S": "5",
    "AQUECIMENTO_S": "30",
    "INCIDENTE_S": "20",
    "INTERVENCAO_APOS_S": "60",
    "DURACAO_S": "150",
}


def compose(*args, env, saida=None):
    comando = ["docker", "compose", "-p", PROJETO, *args]
    print("$", " ".join(comando), flush=True)
    return subprocess.run(comando, cwd=RAIZ, env=env, check=True, stdout=saida, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cenario", choices=CENARIOS, required=True)
    parser.add_argument("--rodada", type=int, default=1)
    parser.add_argument("--replicas", type=int, help="nº de réplicas do controle (padrão 30)")
    parser.add_argument("--sobrescrever", action="store_true", help="apaga a pasta da execução se já existir")
    args = parser.parse_args()

    execucao = f"{args.cenario}_r{args.rodada}"
    pasta = RAIZ / "logs" / execucao
    if pasta.exists() and any(pasta.iterdir()):
        if not args.sobrescrever:
            sys.exit(f"logs/{execucao} já existe. Use outra --rodada ou --sobrescrever.")
        for arquivo in pasta.iterdir():
            arquivo.unlink()
    pasta.mkdir(parents=True, exist_ok=True)

    parametros = dict(PADROES)
    parametros.update(CENARIOS[args.cenario])
    if args.replicas:
        parametros["REPLICAS"] = str(args.replicas)
    parametros["EXECUCAO"] = execucao
    env = {**os.environ, **parametros}

    versao_docker = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True
    ).stdout.strip()
    registro = {
        "execucao": execucao,
        "cenario": args.cenario,
        "rodada": args.rodada,
        "parametros": parametros,
        "inicio": datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "cpus_host": os.cpu_count(),
        "docker": versao_docker,
    }

    compose("down", "--remove-orphans", env=env)
    compose("up", "-d", "--build", env=env)
    ids = subprocess.run(
        ["docker", "compose", "-p", PROJETO, "ps", "-a", "-q", "cliente", "injetor"],
        cwd=RAIZ, env=env, capture_output=True, text=True, check=True,
    ).stdout.split()
    print(f"Executando o roteiro (~{parametros['DURACAO_S']} s). Aguardando cliente e injetor terminarem...")
    inicio = time.monotonic()
    subprocess.run(["docker", "wait", *ids], check=True, stdout=subprocess.DEVNULL)
    registro["duracao_real_s"] = round(time.monotonic() - inicio, 1)

    with open(pasta / "docker_compose.log", "w", encoding="utf-8") as arquivo:
        compose("logs", "--no-color", "--timestamps", env=env, saida=arquivo)
    compose("down", "--remove-orphans", env=env)

    with open(pasta / "parametros.json", "w", encoding="utf-8") as arquivo:
        json.dump(registro, arquivo, indent=2, ensure_ascii=False)

    subprocess.run([sys.executable, str(RAIZ / "analisar.py"), str(pasta)], check=True)
    subprocess.run([sys.executable, str(RAIZ / "analisar.py"), "--comparar"], check=True)


if __name__ == "__main__":
    main()
