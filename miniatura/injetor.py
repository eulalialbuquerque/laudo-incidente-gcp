"""
injetor: executa o roteiro do incidente (papel da automação que gravou a
política e da equipe que reagiu).

  t = AQUECIMENTO_S                       grava a política com campo em branco
  t = AQUECIMENTO_S + INCIDENTE_S         "botão vermelho": volta a política válida
  t = ... + INTERVENCAO_APOS_S            intervenção manual: liga a proteção no
                                          banco de políticas (0 = não intervém)
  t = DURACAO_S                           fim

Todos os marcos vão para eventos.csv, que é a referência de tempo da análise.
"""

import json
import time
import urllib.request

from comum import LogCSV, env_float
import os

POLITICAS_URL = os.getenv("POLITICAS_URL", "http://politicas:8000")
AQUECIMENTO_S = env_float("AQUECIMENTO_S", 30)
INCIDENTE_S = env_float("INCIDENTE_S", 20)
INTERVENCAO_APOS_S = env_float("INTERVENCAO_APOS_S", 60)
DURACAO_S = env_float("DURACAO_S", 150)

POLITICA_EM_BRANCO = {"versao": 2, "projeto": "origem", "limite_por_minuto": None}
POLITICA_CORRIGIDA = {"versao": 3, "projeto": "origem", "limite_por_minuto": 100}

eventos = LogCSV("eventos.csv", ["evento", "detalhe"])


def post(rota, corpo=None):
    dados = json.dumps(corpo or {}).encode()
    requisicao = urllib.request.Request(
        POLITICAS_URL + rota, data=dados, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(requisicao, timeout=5) as resposta:
        return resposta.status


def esperar_politicas():
    while True:
        try:
            with urllib.request.urlopen(POLITICAS_URL + "/saude", timeout=2):
                return
        except Exception:
            time.sleep(0.5)


def dormir_ate(inicio, segundos):
    restante = inicio + segundos - time.monotonic()
    if restante > 0:
        time.sleep(restante)


def main():
    esperar_politicas()
    inicio = time.monotonic()
    eventos.escrever(
        "inicio",
        f"aquecimento_s={AQUECIMENTO_S} incidente_s={INCIDENTE_S} "
        f"intervencao_apos_s={INTERVENCAO_APOS_S} duracao_s={DURACAO_S}",
    )

    dormir_ate(inicio, AQUECIMENTO_S)
    post("/admin/politica", POLITICA_EM_BRANCO)
    eventos.escrever("politica_em_branco", json.dumps(POLITICA_EM_BRANCO))

    dormir_ate(inicio, AQUECIMENTO_S + INCIDENTE_S)
    post("/admin/politica", POLITICA_CORRIGIDA)
    eventos.escrever("botao_vermelho", json.dumps(POLITICA_CORRIGIDA))

    if INTERVENCAO_APOS_S > 0:
        dormir_ate(inicio, AQUECIMENTO_S + INCIDENTE_S + INTERVENCAO_APOS_S)
        post("/admin/protecao")
        eventos.escrever("intervencao_manual", "protecao ligada no banco de politicas")

    dormir_ate(inicio, DURACAO_S)
    eventos.escrever("fim", "")


if __name__ == "__main__":
    main()
