"""
cliente: gera carga contínua contra as réplicas do controle (papel dos
clientes das APIs do Google Cloud) e registra cada requisição.

É daqui que saem o tempo até a falha, o tempo até a recuperação e a
porcentagem de requisições com erro.

O nome "controle" no DNS interno do Docker devolve o IP de todas as réplicas;
a cada requisição o cliente sorteia uma delas (balanceamento simples).
Para testar fora do Docker, CONTROLE_ENDERECOS=host:porta,host:porta,...
"""

import os
import random
import socket
import threading
import time
import urllib.error
import urllib.request

from comum import LogCSV, env_float, env_int

CONTROLE_HOST = os.getenv("CONTROLE_HOST", "controle")
CONTROLE_PORTA = env_int("CONTROLE_PORTA", 8080)
CONTROLE_ENDERECOS = os.getenv("CONTROLE_ENDERECOS", "")
DURACAO_S = env_float("DURACAO_S", 150)
THREADS = env_int("THREADS", 8)
INTERVALO_S = env_float("INTERVALO_S", 0.1)
TIMEOUT_S = env_float("TIMEOUT_S", 1.0)

log = LogCSV("cliente.csv", ["alvo", "resultado", "latencia_ms"])
eventos = LogCSV("cliente_eventos.csv", ["evento", "detalhe"])
enderecos = []


def resolver():
    if CONTROLE_ENDERECOS:
        lista = []
        for item in CONTROLE_ENDERECOS.split(","):
            host, porta = item.rsplit(":", 1)
            lista.append((host, int(porta)))
        return lista
    infos = socket.getaddrinfo(CONTROLE_HOST, CONTROLE_PORTA, type=socket.SOCK_STREAM)
    return sorted({(info[4][0], CONTROLE_PORTA) for info in infos})


def atualizar_enderecos(fim):
    global enderecos
    ultimo = -1
    while time.monotonic() < fim:
        try:
            enderecos = resolver()
            if len(enderecos) != ultimo:
                eventos.escrever("replicas_resolvidas", len(enderecos))
                ultimo = len(enderecos)
        except OSError as erro:
            eventos.escrever("dns_falhou", type(erro).__name__)
        time.sleep(2)


def gerar_carga(fim):
    while time.monotonic() < fim:
        if not enderecos:
            time.sleep(0.2)
            continue
        host, porta = random.choice(enderecos)
        alvo = f"{host}:{porta}"
        inicio = time.monotonic()
        try:
            with urllib.request.urlopen(f"http://{alvo}/checar", timeout=TIMEOUT_S) as resposta:
                resposta.read()
                resultado = str(resposta.status)
        except urllib.error.HTTPError as erro:
            resultado = str(erro.code)
        except Exception as erro:
            causa = getattr(erro, "reason", erro)
            resultado = "erro_" + type(causa).__name__
        log.escrever(alvo, resultado, round((time.monotonic() - inicio) * 1000))
        time.sleep(INTERVALO_S)


def main():
    fim = time.monotonic() + DURACAO_S
    eventos.escrever("inicio", f"threads={THREADS} intervalo_s={INTERVALO_S} duracao_s={DURACAO_S}")
    threading.Thread(target=atualizar_enderecos, args=(fim,), daemon=True).start()
    trabalhadores = [threading.Thread(target=gerar_carga, args=(fim,)) for _ in range(THREADS)]
    for t in trabalhadores:
        t.start()
    for t in trabalhadores:
        t.join()
    eventos.escrever("fim", "")


if __name__ == "__main__":
    main()
