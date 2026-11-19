"""
Analisa os logs brutos de uma execução e gera as métricas do laudo.

    python analisar.py logs/sem_backoff_r1     # uma execução
    python analisar.py --comparar              # tabela com todas as execuções

Gera, dentro da pasta da execução:
  resumo.md               métricas, cada uma com o arquivo de log de onde saiu
  serie_por_segundo.csv   a linha do tempo segundo a segundo
  grafico.svg             % de erro do cliente e réplicas de pé ao longo do tempo
E, com --comparar: logs/comparacao.md e logs/comparacao.svg.

Definições (t = 0 no evento politica_em_branco de eventos.csv):
  erro                      toda resposta do cliente diferente de HTTP 200
  tempo até a falha         1º segundo t >= 0 com erro >= 50 % das requisições
  tempo até a recuperação   a partir do botão vermelho, 1º segundo que inicia
                            JANELA_ESTAVEL segundos seguidos com erro <= 5 %
  trabalho desperdiçado     leitura atendida pelo banco de políticas depois do
                            prazo (TIMEOUT_S) do controle, que já tinha desistido
"""

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
LIMIAR_FALHA = 50.0
LIMIAR_RECUPERADO = 5.0
JANELA_ESTAVEL = 5
BASE_S = 10  # segundos antes da injeção usados como linha de base


def ler_csv(caminho):
    if not caminho.exists():
        return []
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def fmt(valor, casas=1, sufixo=""):
    if valor is None:
        return "não ocorreu"
    return f"{valor:.{casas}f}".replace(".", ",") + sufixo


def texto_recuperacao(m):
    if not m.get("houve_falha", True):
        return "sem falha"
    return fmt(m["recuperacao_s_apos_botao"], 1, " s") if m["recuperacao_s_apos_botao"] is not None else "não recuperou"


def texto_antes_intervencao(m):
    if not m.get("houve_falha", True):
        return "sem falha"
    if m["intervencao_s"] is None:
        return "sem intervenção"
    antes = m["recuperou_antes_da_intervencao"]
    return "sim" if antes else ("não" if antes is False else "não recuperou")


def analisar(pasta):
    pasta = Path(pasta)
    parametros = json.loads((pasta / "parametros.json").read_text(encoding="utf-8")) if (
        pasta / "parametros.json").exists() else {"parametros": {}, "cenario": pasta.name}
    p = parametros.get("parametros", {})
    timeout_ms = float(p.get("TIMEOUT_S", 1.0)) * 1000
    replicas_total = int(p.get("REPLICAS", 0)) or None

    eventos = {linha["evento"]: float(linha["ts"]) for linha in ler_csv(pasta / "eventos.csv")}
    if "politica_em_branco" not in eventos:
        sys.exit(f"{pasta}/eventos.csv não tem o evento politica_em_branco: a execução terminou antes?")
    t0 = eventos["politica_em_branco"]
    rel = {nome: ts - t0 for nome, ts in eventos.items()}

    cliente = ler_csv(pasta / "cliente.csv")
    politicas = ler_csv(pasta / "politicas.csv")
    controles = sorted(pasta.glob("controle_*.csv"))

    # --- cliente: total e erros por segundo ---
    por_seg = defaultdict(lambda: {"total": 0, "erros": 0, "pol_chegadas": 0, "pol_no_prazo": 0,
                                   "pol_desperdicio": 0, "pol_recusadas": 0, "pol_ocupacao_max": 0,
                                   "quedas": 0})
    tipos_erro = defaultdict(int)
    for linha in cliente:
        s = int((float(linha["ts"]) - t0) // 1)
        por_seg[s]["total"] += 1
        if linha["resultado"] != "200":
            por_seg[s]["erros"] += 1
            if s >= 0:
                tipos_erro[linha["resultado"]] += 1

    # --- banco de políticas ---
    for linha in politicas:
        # ts é o fim do atendimento; a chegada foi total_ms antes
        chegada = float(linha["ts"]) - float(linha["total_ms"] or 0) / 1000
        s = int((chegada - t0) // 1)
        d = por_seg[s]
        d["pol_chegadas"] += 1
        d["pol_ocupacao_max"] = max(d["pol_ocupacao_max"], int(linha["no_servidor"] or 0))
        if linha["resultado"] == "recusada":
            d["pol_recusadas"] += 1
        elif float(linha["total_ms"]) <= timeout_ms:
            d["pol_no_prazo"] += 1
        else:
            d["pol_desperdicio"] += 1

    # --- réplicas: quedas e quantas estão com política carregada ---
    mudancas = []  # (ts, replica, +1/-1)
    replicas = set()
    quedas_total = 0
    for arquivo in controles:
        de_pe = False
        for linha in ler_csv(arquivo):
            ts, replica, evento = float(linha["ts"]), linha["replica"], linha["evento"]
            replicas.add(replica)
            if evento == "politica_carregada" and not de_pe:
                mudancas.append((ts, replica, +1))
                de_pe = True
            elif evento == "processo_encerrado":
                if de_pe:
                    mudancas.append((ts, replica, -1))
                    de_pe = False
                if "codigo=0" not in linha["detalhe"]:
                    por_seg[int((ts - t0) // 1)]["quedas"] += 1
                    if ts >= t0:
                        quedas_total += 1
    mudancas.sort()
    replicas_total = replicas_total or len(replicas)

    if not por_seg:
        sys.exit(f"{pasta}: nenhum dado")
    inicio = max(min(por_seg), -BASE_S)
    fim = max(s for s, d in por_seg.items() if d["total"] > 0)
    serie, de_pe, i = [], 0, 0
    for s in range(inicio, fim + 1):
        limite = t0 + s + 1
        while i < len(mudancas) and mudancas[i][0] < limite:
            de_pe += mudancas[i][2]
            i += 1
        d = por_seg[s]
        erro_pct = 100 * d["erros"] / d["total"] if d["total"] else None
        serie.append({"t": s, **d, "erro_pct": erro_pct, "replicas_de_pe": de_pe})

    # --- métricas ---
    def janela(a, b):
        linhas = [x for x in serie if a <= x["t"] < b]
        total = sum(x["total"] for x in linhas)
        erros = sum(x["erros"] for x in linhas)
        return total, erros, (100 * erros / total if total else None)

    _, _, erro_base = janela(-BASE_S, 0)
    primeiro_erro = next((float(l["ts"]) - t0 for l in cliente
                          if float(l["ts"]) >= t0 and l["resultado"] != "200"), None)
    t_falha = next((x["t"] for x in serie if x["t"] >= 0 and x["erro_pct"] is not None
                    and x["erro_pct"] >= LIMIAR_FALHA), None)

    t_bv = rel.get("botao_vermelho")
    t_rec = None
    if t_bv is not None:
        candidatos = [x for x in serie if x["t"] >= int(t_bv // 1)]
        for k in range(len(candidatos) - JANELA_ESTAVEL + 1):
            bloco = candidatos[k:k + JANELA_ESTAVEL]
            if all(x["erro_pct"] is not None and x["erro_pct"] <= LIMIAR_RECUPERADO for x in bloco):
                t_rec = bloco[0]["t"]
                break
    houve_falha = t_falha is not None
    # Sem falha não há o que recuperar. O max() evita valor negativo quando o
    # segundo estável começa no mesmo segundo do botão vermelho.
    rec_apos_bv = max(0.0, t_rec - t_bv) if (houve_falha and t_rec is not None) else None
    t_int = rel.get("intervencao_manual")
    recuperou_antes_intervencao = None
    if houve_falha and t_rec is not None and t_int is not None:
        recuperou_antes_intervencao = t_rec < t_int

    total_inc, erros_inc, erro_inc = janela(0, fim + 1)
    fim_janela_rec = t_rec if t_rec is not None else fim + 1
    total_bv, erros_bv, erro_bv = janela(int(t_bv // 1), fim_janela_rec) if t_bv is not None else (0, 0, None)

    pos_bv = [x for x in serie if t_bv is not None and int(t_bv // 1) <= x["t"] < fim_janela_rec]
    chegadas_bv = sum(x["pol_chegadas"] for x in pos_bv)
    atendidas_bv = sum(x["pol_no_prazo"] + x["pol_desperdicio"] for x in pos_bv)
    desperdicio_bv = sum(x["pol_desperdicio"] for x in pos_bv)
    recusadas_bv = sum(x["pol_recusadas"] for x in pos_bv)
    ocupacao_max = max((x["pol_ocupacao_max"] for x in serie if x["t"] >= 0), default=0)

    m = {
        "execucao": pasta.name,
        "cenario": parametros.get("cenario", pasta.name),
        "erro_base_pct": erro_base,
        "primeiro_erro_s": primeiro_erro,
        "houve_falha": houve_falha,
        "tempo_ate_falha_s": t_falha,
        "botao_vermelho_s": t_bv,
        "intervencao_s": t_int,
        "recuperacao_s_apos_botao": rec_apos_bv,
        "recuperou_antes_da_intervencao": recuperou_antes_intervencao,
        "erro_pct_desde_injecao": erro_inc,
        "requisicoes_desde_injecao": total_inc,
        "erros_desde_injecao": erros_inc,
        "erro_pct_botao_ate_recuperar": erro_bv,
        "quedas_de_processo": quedas_total,
        "replicas": replicas_total,
        "politicas_chegadas_botao_ate_recuperar": chegadas_bv,
        "politicas_chegadas_por_replica": chegadas_bv / replicas_total if replicas_total else None,
        "politicas_desperdicio_pct": 100 * desperdicio_bv / atendidas_bv if atendidas_bv else None,
        "politicas_recusadas": recusadas_bv,
        "politicas_ocupacao_max": ocupacao_max,
        "tipos_erro": dict(tipos_erro),
    }

    # --- saídas ---
    with open(pasta / "serie_por_segundo.csv", "w", newline="", encoding="utf-8") as arquivo:
        campos = ["t", "total", "erros", "erro_pct", "replicas_de_pe", "quedas", "pol_chegadas",
                  "pol_no_prazo", "pol_desperdicio", "pol_recusadas", "pol_ocupacao_max"]
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        for x in serie:
            escritor.writerow({**x, "erro_pct": "" if x["erro_pct"] is None else round(x["erro_pct"], 1)})
    (pasta / "metricas.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    (pasta / "resumo.md").write_text(resumo_md(m, rel, p), encoding="utf-8")
    (pasta / "grafico.svg").write_text(
        grafico({pasta.name: serie}, rel, replicas_total), encoding="utf-8")
    print(f"{pasta.name}: falha em {fmt(t_falha, 0, ' s')}, recuperação {texto_recuperacao(m)} "
          f"após o botão vermelho, erro desde a injeção {fmt(erro_inc, 1, ' %')}")
    return m, serie, rel


def resumo_md(m, rel, p):
    fonte_cli = "`cliente.csv` (via `serie_por_segundo.csv`)"
    fonte_pol = "`politicas.csv` (via `serie_por_segundo.csv`)"
    linhas = [
        f"# Resumo da execução `{m['execucao']}`",
        "",
        "Gerado por `analisar.py` a partir dos logs brutos desta pasta. t = 0 é o evento "
        "`politica_em_branco` de `eventos.csv`.",
        "",
        "## Marcos (`eventos.csv`)",
        "",
        "| Evento | t (s) |",
        "|---|---:|",
    ]
    for nome, t in sorted(rel.items(), key=lambda item: item[1]):
        linhas.append(f"| {nome} | {fmt(t, 1)} |")
    linhas += [
        "",
        "## Métricas",
        "",
        "| Métrica | Valor | Fonte |",
        "|---|---:|---|",
        f"| Erro na linha de base ({BASE_S} s antes da injeção) | {fmt(m['erro_base_pct'], 1, ' %')} | {fonte_cli} |",
        f"| Primeira requisição com erro após a injeção | {fmt(m['primeiro_erro_s'], 1, ' s')} | `cliente.csv` |",
        f"| **Tempo até a falha** (erro >= {LIMIAR_FALHA:.0f} %) | {fmt(m['tempo_ate_falha_s'], 0, ' s')} | {fonte_cli} |",
        f"| **Tempo até a recuperação** após o botão vermelho ({JANELA_ESTAVEL} s seguidos com erro <= {LIMIAR_RECUPERADO:.0f} %) | {texto_recuperacao(m)} | {fonte_cli} + `eventos.csv` |",
        f"| Recuperou antes da intervenção manual? | {texto_antes_intervencao(m)} | `eventos.csv` |",
        f"| **% de requisições com erro** desde a injeção | {fmt(m['erro_pct_desde_injecao'], 1, ' %')} ({m['erros_desde_injecao']} de {m['requisicoes_desde_injecao']}) | {fonte_cli} |",
        f"| % de erro entre o botão vermelho e a recuperação | {fmt(m['erro_pct_botao_ate_recuperar'], 1, ' %')} | {fonte_cli} |",
        f"| Quedas de processo do controle (após a injeção) | {m['quedas_de_processo']} | `controle_*.csv` |",
        f"| Leituras pedidas ao banco entre o botão vermelho e a recuperação | {m['politicas_chegadas_botao_ate_recuperar']} ({fmt(m['politicas_chegadas_por_replica'], 1)} por réplica) | {fonte_pol} |",
        f"| Leituras atendidas depois que o controle já tinha desistido (desperdício) | {fmt(m['politicas_desperdicio_pct'], 1, ' %')} | {fonte_pol} |",
        f"| Leituras recusadas com 503 no mesmo período | {m['politicas_recusadas']} | {fonte_pol} |",
        f"| Máximo de leituras dentro do banco ao mesmo tempo | {m['politicas_ocupacao_max']} | `politicas.csv` |",
        "",
        "## Tipos de erro vistos pelo cliente após a injeção (`cliente.csv`)",
        "",
        "| Resultado | Requisições |",
        "|---|---:|",
    ]
    for tipo, n in sorted(m["tipos_erro"].items(), key=lambda item: -item[1]):
        linhas.append(f"| {tipo} | {n} |")
    linhas += ["", "## Parâmetros", "", "```json", json.dumps(p, indent=2, ensure_ascii=False), "```", ""]
    return "\n".join(linhas)


CORES = ["#c0392b", "#2471a3", "#1e8449", "#7d3c98", "#b9770e", "#566573"]


def grafico(series, rel, replicas_total, largura=980, altura=360):
    """SVG simples: % de erro do cliente por segundo (e réplicas de pé, se só uma série)."""
    margem_e, margem_d, margem_t, margem_b = 55, 175, 30, 45
    todos_t = [x["t"] for serie in series.values() for x in serie]
    t_min, t_max = min(todos_t), max(todos_t)
    w, h = largura - margem_e - margem_d, altura - margem_t - margem_b

    def X(t):
        return margem_e + (t - t_min) / max(1, t_max - t_min) * w

    def Y(pct):
        return margem_t + h - pct / 100 * h

    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
              f'font-family="sans-serif" font-size="12">',
              f'<rect width="{largura}" height="{altura}" fill="white"/>']
    for pct in (0, 25, 50, 75, 100):
        partes.append(f'<line x1="{margem_e}" x2="{margem_e + w}" y1="{Y(pct):.1f}" y2="{Y(pct):.1f}" stroke="#e5e5e5"/>')
        partes.append(f'<text x="{margem_e - 8}" y="{Y(pct) + 4:.1f}" text-anchor="end">{pct}%</text>')
    passo = 10 if t_max - t_min <= 200 else 30
    for t in range((t_min // passo) * passo, t_max + 1, passo):
        if t >= t_min:
            partes.append(f'<text x="{X(t):.1f}" y="{margem_t + h + 16}" text-anchor="middle">{t}</text>')
    partes.append(f'<text x="{margem_e + w / 2}" y="{altura - 8}" text-anchor="middle">'
                  f'segundos desde a política em branco</text>')
    partes.append(f'<text x="14" y="{margem_t + h / 2}" transform="rotate(-90 14 {margem_t + h / 2})" '
                  f'text-anchor="middle">% de requisições com erro</text>')
    marcos = [(n, t) for n, t in rel.items()
              if n in ("politica_em_branco", "botao_vermelho", "intervencao_manual") and t_min <= t <= t_max]
    for k, (nome, t) in enumerate(marcos):
            partes.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{margem_t}" y2="{margem_t + h}" '
                          f'stroke="#555" stroke-dasharray="4 3"/>')
            partes.append(f'<text x="{X(t) + 4:.1f}" y="{margem_t + 12 + 14 * (k % 2)}" fill="#555">{nome.replace("_", " ")}</text>')
    if len(series) == 1 and replicas_total:
        serie = next(iter(series.values()))
        pontos = " ".join(f"{X(x['t']):.1f},{Y(100 * x['replicas_de_pe'] / replicas_total):.1f}" for x in serie)
        partes.append(f'<polyline points="{pontos}" fill="none" stroke="#7f8c8d" stroke-width="1.5" stroke-dasharray="2 2"/>')
        y_leg = margem_t + 20 + 18 * len(series)
        partes.append(f'<line x1="{margem_e + w + 12}" x2="{margem_e + w + 32}" y1="{y_leg - 4}" y2="{y_leg - 4}" stroke="#7f8c8d" stroke-width="1.5" stroke-dasharray="2 2"/>')
        partes.append(f'<text x="{margem_e + w + 38}" y="{y_leg}" fill="#555">réplicas de pé</text>')
        partes.append(f'<text x="{margem_e + w + 38}" y="{y_leg + 14}" fill="#555">({replicas_total} = 100%)</text>')
    for k, (nome, serie) in enumerate(series.items()):
        cor = CORES[k % len(CORES)]
        pontos = " ".join(f"{X(x['t']):.1f},{Y(x['erro_pct']):.1f}" for x in serie if x["erro_pct"] is not None)
        partes.append(f'<polyline points="{pontos}" fill="none" stroke="{cor}" stroke-width="2"/>')
        y_leg = margem_t + 20 + 18 * k
        partes.append(f'<line x1="{margem_e + w + 12}" x2="{margem_e + w + 32}" y1="{y_leg - 4}" y2="{y_leg - 4}" stroke="{cor}" stroke-width="2"/>')
        partes.append(f'<text x="{margem_e + w + 38}" y="{y_leg}" fill="#333">erro: {nome}</text>')
    partes.append("</svg>")
    return "\n".join(partes)


def comparar():
    pastas = sorted(p.parent for p in (RAIZ / "logs").glob("*/parametros.json"))
    if not pastas:
        sys.exit("Nenhuma execução em logs/ (falta parametros.json).")
    resultados = []
    for pasta in pastas:
        m = json.loads((pasta / "metricas.json").read_text(encoding="utf-8")) if (
            pasta / "metricas.json").exists() else analisar(pasta)[0]
        resultados.append(m)

    linhas = [
        "# Comparação entre execuções",
        "",
        "Gerado por `python analisar.py --comparar` a partir de `logs/<execucao>/metricas.json`, "
        "que por sua vez vem dos CSV brutos de cada pasta (ver `resumo.md` de cada execução).",
        "",
        "| Execução | Tempo até a falha (s) | Recuperação após o botão vermelho (s) | Antes da intervenção? | % erro desde a injeção | Leituras ao banco por réplica (botão → recuperação) | Desperdício no banco | Quedas |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for m in resultados:
        linhas.append(
            f"| `{m['execucao']}` | {fmt(m['tempo_ate_falha_s'], 0)} | {texto_recuperacao(m)} "
            f"| {texto_antes_intervencao(m)} "
            f"| {fmt(m['erro_pct_desde_injecao'], 1, ' %')} | {fmt(m['politicas_chegadas_por_replica'], 1)} "
            f"| {fmt(m['politicas_desperdicio_pct'], 1, ' %')} | {m['quedas_de_processo']} |"
        )

    por_cenario = defaultdict(list)
    for m in resultados:
        por_cenario[m["cenario"]].append(m)
    linhas += ["", "## Mediana por cenário", "",
               "| Cenário | Rodadas | Recuperação (s, mediana) | % erro desde a injeção (mediana) |",
               "|---|---:|---:|---:|"]
    for cenario, ms in por_cenario.items():
        com_falha = [m for m in ms if m.get("houve_falha", True)]
        recs = [m["recuperacao_s_apos_botao"] for m in com_falha if m["recuperacao_s_apos_botao"] is not None]
        erros = [m["erro_pct_desde_injecao"] for m in ms if m["erro_pct_desde_injecao"] is not None]
        nao_rec = len(com_falha) - len(recs)
        if not com_falha:
            rec_txt = "sem falha"
        else:
            rec_txt = fmt(statistics.median(recs), 1) if recs else "não recuperou"
        if recs and nao_rec:
            rec_txt += f" ({nao_rec} rodada(s) sem recuperar)"
        linhas.append(f"| {cenario} | {len(ms)} | {rec_txt} | {fmt(statistics.median(erros), 1, ' %') if erros else '—'} |")
    (RAIZ / "logs" / "comparacao.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    # gráfico com a 1ª rodada de cada cenário
    series, rel = {}, {}
    for pasta in pastas:
        params = json.loads((pasta / "parametros.json").read_text(encoding="utf-8"))
        if params.get("cenario") in {s.rsplit("_r", 1)[0] for s in series}:
            continue
        serie = []
        for linha in ler_csv(pasta / "serie_por_segundo.csv"):
            serie.append({"t": int(linha["t"]), "erro_pct": float(linha["erro_pct"]) if linha["erro_pct"] else None})
        series[pasta.name] = serie
        if not rel:
            eventos = {l["evento"]: float(l["ts"]) for l in ler_csv(pasta / "eventos.csv")}
            rel = {k: v - eventos["politica_em_branco"] for k, v in eventos.items()}
    (RAIZ / "logs" / "comparacao.svg").write_text(grafico(series, rel, None), encoding="utf-8")
    print("Comparação salva em logs/comparacao.md e logs/comparacao.svg")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pastas", nargs="*")
    parser.add_argument("--comparar", action="store_true")
    args = parser.parse_args()
    for pasta in args.pastas:
        analisar(pasta)
    if args.comparar:
        comparar()
    if not args.pastas and not args.comparar:
        parser.print_help()


if __name__ == "__main__":
    main()
