# Resumo da execução `sem_backoff_r2`

Gerado por `analisar.py` a partir dos logs brutos desta pasta. t = 0 é o evento `politica_em_branco` de `eventos.csv`.

## Marcos (`eventos.csv`)

| Evento | t (s) |
|---|---:|
| inicio | -29,9 |
| politica_em_branco | 0,0 |
| botao_vermelho | 19,9 |
| intervencao_manual | 79,8 |
| fim | 119,0 |

## Métricas

| Métrica | Valor | Fonte |
|---|---:|---|
| Erro na linha de base (10 s antes da injeção) | não ocorreu | `cliente.csv` (via `serie_por_segundo.csv`) |
| Primeira requisição com erro após a injeção | 57,6 s | `cliente.csv` |
| **Tempo até a falha** (erro >= 50 %) | 59 s | `cliente.csv` (via `serie_por_segundo.csv`) |
| **Tempo até a recuperação** após o botão vermelho (5 s seguidos com erro <= 5 %) | 42,1 s | `cliente.csv` (via `serie_por_segundo.csv`) + `eventos.csv` |
| Recuperou antes da intervenção manual? | sim | `eventos.csv` |
| **% de requisições com erro** desde a injeção | 0,3 % (25 de 9697) | `cliente.csv` (via `serie_por_segundo.csv`) |
| % de erro entre o botão vermelho e a recuperação | 12,7 % | `cliente.csv` (via `serie_por_segundo.csv`) |
| Quedas de processo do controle (após a injeção) | 101 | `controle_*.csv` |
| Leituras pedidas ao banco entre o botão vermelho e a recuperação | 159 (5,3 por réplica) | `politicas.csv` (via `serie_por_segundo.csv`) |
| Leituras atendidas depois que o controle já tinha desistido (desperdício) | 10,1 % | `politicas.csv` (via `serie_por_segundo.csv`) |
| Leituras recusadas com 503 no mesmo período | 0 | `politicas.csv` (via `serie_por_segundo.csv`) |
| Máximo de leituras dentro do banco ao mesmo tempo | 15 | `politicas.csv` |

## Tipos de erro vistos pelo cliente após a injeção (`cliente.csv`)

| Resultado | Requisições |
|---|---:|
| erro_ConnectionRefusedError | 17 |
| erro_TimeoutError | 5 |
| 503 | 3 |

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
  "BACKOFF": "sem_backoff",
  "VALIDAR": "0",
  "EXECUCAO": "sem_backoff_r2"
}
```
