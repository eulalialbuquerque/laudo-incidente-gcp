# Resumo da execução `jitter_r2`

Gerado por `analisar.py` a partir dos logs brutos desta pasta. t = 0 é o evento `politica_em_branco` de `eventos.csv`.

## Marcos (`eventos.csv`)

| Evento | t (s) |
|---|---:|
| inicio | -32,4 |
| politica_em_branco | 0,0 |
| botao_vermelho | 19,9 |
| intervencao_manual | 81,7 |
| fim | 119,6 |

## Métricas

| Métrica | Valor | Fonte |
|---|---:|---|
| Erro na linha de base (10 s antes da injeção) | não ocorreu | `cliente.csv` (via `serie_por_segundo.csv`) |
| Primeira requisição com erro após a injeção | 101,8 s | `cliente.csv` |
| **Tempo até a falha** (erro >= 50 %) | não ocorreu | `cliente.csv` (via `serie_por_segundo.csv`) |
| **Tempo até a recuperação** após o botão vermelho (5 s seguidos com erro <= 5 %) | sem falha | `cliente.csv` (via `serie_por_segundo.csv`) + `eventos.csv` |
| Recuperou antes da intervenção manual? | sem falha | `eventos.csv` |
| **% de requisições com erro** desde a injeção | 0,2 % (20 de 10745) | `cliente.csv` (via `serie_por_segundo.csv`) |
| % de erro entre o botão vermelho e a recuperação | 4,7 % | `cliente.csv` (via `serie_por_segundo.csv`) |
| Quedas de processo do controle (após a injeção) | 40 | `controle_*.csv` |
| Leituras pedidas ao banco entre o botão vermelho e a recuperação | 258 (8,6 por réplica) | `politicas.csv` (via `serie_por_segundo.csv`) |
| Leituras atendidas depois que o controle já tinha desistido (desperdício) | 4,8 % | `politicas.csv` (via `serie_por_segundo.csv`) |
| Leituras recusadas com 503 no mesmo período | 51 | `politicas.csv` (via `serie_por_segundo.csv`) |
| Máximo de leituras dentro do banco ao mesmo tempo | 8 | `politicas.csv` |

## Tipos de erro vistos pelo cliente após a injeção (`cliente.csv`)

| Resultado | Requisições |
|---|---:|
| erro_ConnectionRefusedError | 20 |

## Parâmetros

```json
{
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
  "BACKOFF": "jitter",
  "VALIDAR": "0",
  "EXECUCAO": "jitter_r2"
}
```
