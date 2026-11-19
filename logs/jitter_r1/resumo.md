# Resumo da execução `jitter_r1`

Gerado por `analisar.py` a partir dos logs brutos desta pasta. t = 0 é o evento `politica_em_branco` de `eventos.csv`.

## Marcos (`eventos.csv`)

| Evento | t (s) |
|---|---:|
| inicio | -30,0 |
| politica_em_branco | 0,0 |
| botao_vermelho | 20,0 |
| intervencao_manual | 80,0 |
| fim | 120,0 |

## Métricas

| Métrica | Valor | Fonte |
|---|---:|---|
| Erro na linha de base (10 s antes da injeção) | 0,0 % | `cliente.csv` (via `serie_por_segundo.csv`) |
| Primeira requisição com erro após a injeção | 0,6 s | `cliente.csv` |
| **Tempo até a falha** (erro >= 50 %) | 3 s | `cliente.csv` (via `serie_por_segundo.csv`) |
| **Tempo até a recuperação** após o botão vermelho (5 s seguidos com erro <= 5 %) | 5,0 s | `cliente.csv` (via `serie_por_segundo.csv`) + `eventos.csv` |
| Recuperou antes da intervenção manual? | sim | `eventos.csv` |
| **% de requisições com erro** desde a injeção | 9,6 % (982 de 10274) | `cliente.csv` (via `serie_por_segundo.csv`) |
| % de erro entre o botão vermelho e a recuperação | 26,9 % | `cliente.csv` (via `serie_por_segundo.csv`) |
| Quedas de processo do controle (após a injeção) | 46 | `controle_*.csv` |
| Leituras pedidas ao banco entre o botão vermelho e a recuperação | 25 (0,8 por réplica) | `politicas.csv` (via `serie_por_segundo.csv`) |
| Leituras atendidas depois que o controle já tinha desistido (desperdício) | 0,0 % | `politicas.csv` (via `serie_por_segundo.csv`) |
| Leituras recusadas com 503 no mesmo período | 0 | `politicas.csv` (via `serie_por_segundo.csv`) |
| Máximo de leituras dentro do banco ao mesmo tempo | 34 | `politicas.csv` |

## Tipos de erro vistos pelo cliente após a injeção (`cliente.csv`)

| Resultado | Requisições |
|---|---:|
| 503 | 903 |
| erro_ConnectionRefusedError | 78 |
| erro_ConnectionResetError | 1 |

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
  "EXECUCAO": "jitter_r1"
}
```
