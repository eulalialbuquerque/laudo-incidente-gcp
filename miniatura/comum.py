"""Utilitários compartilhados pelos serviços da miniatura: configuração e log CSV."""

import csv
import os
import threading
import time

PASTA_LOGS = os.getenv("PASTA_LOGS", "/logs")


def env_float(nome, padrao):
    valor = os.getenv(nome, "").strip()
    return float(valor) if valor else float(padrao)


def env_int(nome, padrao):
    valor = os.getenv(nome, "").strip()
    return int(valor) if valor else int(padrao)


class LogCSV:
    """
    Arquivo CSV de log bruto. Cada linha começa com o instante em segundos
    desde a época Unix (todos os containers usam o relógio do mesmo host, então
    os arquivos podem ser cruzados). Abre em modo de acréscimo: o controle é
    reiniciado várias vezes e continua escrevendo no mesmo arquivo.
    """

    def __init__(self, nome, campos):
        os.makedirs(PASTA_LOGS, exist_ok=True)
        caminho = os.path.join(PASTA_LOGS, nome)
        novo = not os.path.exists(caminho) or os.path.getsize(caminho) == 0
        self._arquivo = open(caminho, "a", newline="", encoding="utf-8")
        self._escritor = csv.writer(self._arquivo)
        self._trava = threading.Lock()
        if novo:
            self._escritor.writerow(["ts", *campos])
            self._arquivo.flush()

    def escrever(self, *valores):
        with self._trava:
            self._escritor.writerow([f"{time.time():.3f}", *valores])
            self._arquivo.flush()
