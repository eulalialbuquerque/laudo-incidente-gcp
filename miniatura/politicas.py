"""
politicas: o banco de políticas (papel do Spanner no incidente do Google).

Capacidade limitada de propósito: atende CAPACIDADE leituras ao mesmo tempo,
cada uma custando CUSTO_MS. O que chega além disso espera numa fila de até
FILA_MAX requisições; com a fila cheia, responde 503 na hora.

Ponto central do efeito manada: o servidor não sabe se quem pediu ainda está
esperando. Uma leitura que ficou tempo demais na fila é processada mesmo
assim, depois que o cliente já desistiu (timeout) e mandou outra. Esse
trabalho desperdiçado é o que mantém o banco sobrecarregado.

Rotas:
  GET  /politica          política atual (passa pela fila)
  GET  /saude             health check (não passa pela fila)
  POST /admin/politica    troca a política (usado pelo injetor)
  POST /admin/protecao    intervenção manual: passa a recusar na hora tudo o
                          que exceder a capacidade, sem fila
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from comum import LogCSV, env_float, env_int

CAPACIDADE = env_int("CAPACIDADE", 1)
CUSTO_S = env_float("CUSTO_MS", 100) / 1000
FILA_MAX = env_int("FILA_MAX", 100)
PORTA = env_int("PORTA", 8000)

POLITICA_INICIAL = {"versao": 1, "projeto": "origem", "limite_por_minuto": 100}

estado = {"politica": POLITICA_INICIAL, "protecao": False, "no_servidor": 0}
trava = threading.Lock()
vagas = threading.Semaphore(CAPACIDADE)

log = LogCSV("politicas.csv", ["resultado", "espera_ms", "total_ms", "no_servidor", "versao"])
eventos = LogCSV("politicas_eventos.csv", ["evento", "detalhe"])


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass  # o log que interessa vai para o CSV

    def _responder(self, status, corpo):
        dados = json.dumps(corpo).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path == "/saude":
            return self._responder(200, {"status": "ok"})
        if self.path != "/politica":
            return self._responder(404, {"erro": "rota inexistente"})

        chegada = time.monotonic()
        with trava:
            ocupacao = estado["no_servidor"]
            limite = CAPACIDADE if estado["protecao"] else FILA_MAX
            recusar = ocupacao >= limite
            if not recusar:
                estado["no_servidor"] += 1
                ocupacao += 1

        if recusar:
            log.escrever("recusada", 0, 0, ocupacao, "")
            try:
                self._responder(503, {"erro": "sobrecarregado"})
            except OSError:
                pass
            return

        resultado, versao, espera = "atendida", "", 0.0
        try:
            with vagas:
                espera = time.monotonic() - chegada
                time.sleep(CUSTO_S)  # o custo da leitura
                politica = estado["politica"]
                versao = politica.get("versao", "")
            try:
                self._responder(200, politica)
            except OSError:
                resultado = "conexao_perdida"
        finally:
            with trava:
                estado["no_servidor"] -= 1
        total = time.monotonic() - chegada
        log.escrever(resultado, round(espera * 1000), round(total * 1000), ocupacao, versao)

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(tamanho) if tamanho else b""
        if self.path == "/admin/politica":
            politica = json.loads(corpo)
            with trava:
                estado["politica"] = politica
            eventos.escrever("politica_trocada", json.dumps(politica))
            return self._responder(200, {"ok": True})
        if self.path == "/admin/protecao":
            with trava:
                estado["protecao"] = True
            eventos.escrever("protecao_ligada", f"capacidade={CAPACIDADE}")
            return self._responder(200, {"ok": True})
        return self._responder(404, {"erro": "rota inexistente"})


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # O padrão do Python é 5 conexões pendentes; com dezenas de réplicas
    # chegando juntas, o excesso ficaria preso no kernel e não na nossa fila.
    request_queue_size = 512


if __name__ == "__main__":
    eventos.escrever(
        "inicio", f"capacidade={CAPACIDADE} custo_ms={CUSTO_S * 1000:.0f} fila_max={FILA_MAX}"
    )
    print(f"politicas ouvindo na porta {PORTA} (capacidade {CAPACIDADE}, custo {CUSTO_S * 1000:.0f} ms)")
    Servidor(("0.0.0.0", PORTA), Handler).serve_forever()
