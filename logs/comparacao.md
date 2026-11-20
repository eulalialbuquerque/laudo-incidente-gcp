# Comparação entre execuções

Gerado por `python analisar.py --comparar` a partir de `logs/<execucao>/metricas.json`, que por sua vez vem dos CSV brutos de cada pasta (ver `resumo.md` de cada execução).

| Execução | Tempo até a falha (s) | Recuperação após o botão vermelho (s) | Antes da intervenção? | % erro desde a injeção | Leituras ao banco por réplica (botão → recuperação) | Desperdício no banco | Quedas |
|---|---:|---:|---|---:|---:|---:|---:|
| `jitter_r1` | 3 | 5,0 s | sim | 9,6 % | 0,8 | 0,0 % | 46 |
| `jitter_r2` | 3 | 16,8 s | sim | 12,4 % | 3,0 | 43,3 % | 44 |
| `sem_backoff_r1` | 3 | 72,0 s | não | 40,4 % | 214,8 | 96,0 % | 42 |
| `sem_backoff_r2` | 3 | 72,0 s | não | 56,3 % | 264,0 | 95,5 % | 46 |
| `validacao_r1` | não ocorreu | sem falha | sem falha | 0,0 % | 0,0 | não ocorreu | 0 |
| `validacao_r2` | não ocorreu | sem falha | sem falha | 0,0 % | 0,0 | não ocorreu | 0 |

## Mediana por cenário

| Cenário | Rodadas | Recuperação (s, mediana) | % erro desde a injeção (mediana) |
|---|---:|---:|---:|
| jitter | 2 | 10,9 | 11,0 % |
| sem_backoff | 2 | 72,0 | 48,4 % |
| validacao | 2 | sem falha | 0,0 % |
