# Comparação entre execuções

Gerado por `python analisar.py --comparar` a partir de `logs/<execucao>/metricas.json`, que por sua vez vem dos CSV brutos de cada pasta (ver `resumo.md` de cada execução).

| Execução | Tempo até a falha (s) | Recuperação após o botão vermelho (s) | Antes da intervenção? | % erro desde a injeção | Leituras ao banco por réplica (botão → recuperação) | Desperdício no banco | Quedas |
|---|---:|---:|---|---:|---:|---:|---:|
| `jitter_r1` | 3 | 5,0 s | sim | 9,6 % | 0,8 | 0,0 % | 46 |
| `sem_backoff_r1` | 3 | 72,0 s | não | 40,4 % | 214,8 | 96,0 % | 42 |
| `validacao_r1` | não ocorreu | sem falha | sem falha | 0,0 % | 0,0 | não ocorreu | 0 |

## Mediana por cenário

| Cenário | Rodadas | Recuperação (s, mediana) | % erro desde a injeção (mediana) |
|---|---:|---:|---:|
| jitter | 1 | 5,0 | 9,6 % |
| sem_backoff | 1 | 72,0 | 40,4 % |
| validacao | 1 | sem falha | 0,0 % |
