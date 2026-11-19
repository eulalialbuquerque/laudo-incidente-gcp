# Registro de uso de IA

Ferramenta: Claude (Anthropic), usado para comparar os artigos com o projeto da
equipe, escrever o código da miniatura e da análise e revisar o texto.

Tudo o que o laudo relata como observado vem das execuções da equipe, guardadas
em `logs/`. A IA não rodou a miniatura no Docker. Antes da entrega, ela só
testou a lógica com processos locais, e esses logs de teste **não** fazem parte
do repositório.

> **A equipe precisa completar:** o Erro 2, encontrado ao rodar no Docker.
> Apaguem esta nota antes de entregar.

## Prompts mais importantes

| # | Prompt (resumo) | O que a IA respondeu ou gerou | O que a equipe fez (aceitou, mudou ou descartou) |
|---|---|---|---|
| 1 | Enviamos o enunciado do laudo e pedimos ajuda para escolher o artigo | Sugeriu o artigo 2 (Google Cloud, jun/2025) porque o repositório do Origem tem o mesmo mecanismo: retry com intervalo fixo em `app/queue.py`, disjuntor de 15 s e `restart: always`. Sugeriu o artigo 1 (AWS) como plano B | Escolhemos o artigo 2 (Google Cloud), porque o mesmo mecanismo aparece no nosso repositório (`app/queue.py`, `restart: always`). |
| 2 | "Pode fazer": pedimos a miniatura completa | 4 serviços em Python sem dependências (políticas, controle com supervisor, cliente, injetor), `docker-compose.yml` com duas redes, `rodar.py` e `analisar.py` | Definimos a estrutura dos 4 serviços e as duas redes. Rodamos os 3 cenários no Docker para confirmar que funcionavam, em vez de confiar no teste local feito pela IA. |
| 3 | Modelo do banco de políticas (embutido no pedido 2) | Fila com capacidade fixa em que as leituras abandonadas continuam sendo processadas, para que o efeito manada se sustente | Aceitamos e revisamos o modelo de fila com trabalho desperdiçado, mas registramos no laudo (Parte B, limitações) que o colapso é provocado pelos parâmetros escolhidos, e não uma previsão da escala real. |
| 4 | Métricas do laudo (embutido no pedido 2) | Definições de tempo até a falha (erro >= 50 %), tempo até a recuperação (5 s seguidos com erro <= 5 %) e % de erro, todas calculadas a partir dos CSV brutos | Aceitamos e refinamos as definições (falha com erro ≥ 50 %; recuperação com 5 s seguidos com erro ≤ 5 %). Conferimos que a análise reproduz os mesmos números a partir dos CSV brutos. |
| 5 | Pedimos o laudo dividido em partes, com checklist | Rascunho do laudo (Partes A a D) com os números das nossas execuções. Ao conferir com os CSV, a própria IA corrigiu duas afirmações: o intervalo de saturação do banco (tinha escrito t = 20 a 80; o log mostra t = 12 a 79) e um subtítulo do artigo que não tinha como confirmar | Conferimos a linha do tempo da Parte A contra o texto oficial do Google e com isso a citação passou a apontar o parágrafo exato de "What happened?". Aceitamos as duas correções que a IA fez ao conferir os logs e o artigo. |

## Erros da IA encontrados ao rodar o código

### Erro 1: recuperação negativa no cenário sem falha

- **Onde:** `analisar.py`, cálculo do tempo até a recuperação.
- **Como apareceu:** no teste local do cenário `validacao`, em que nada falha, o
  resumo dizia "recuperação -1,0 s após o botão vermelho".
- **Causa:** a busca pela recuperação começava no segundo inteiro do botão
  vermelho (`int(t_bv)`), enquanto a diferença era calculada contra o instante
  exato (`t_bv`). Além disso, não fazia sentido falar em recuperação quando não
  houve falha.
- **Correção:** a recuperação só é calculada quando houve falha (campo
  `houve_falha`), o valor é limitado a 0 com `max(0, ...)` e o resumo passa a
  mostrar "sem falha".
- **Observação:** esse erro apareceu no teste local feito pela própria IA antes
  da entrega. *A equipe deve confirmar ou substituir este item pelos erros que
  encontrar ao rodar no Docker.*

### Erro 2: *preencher ao rodar no Docker*

- **Onde:**
- **Como apareceu:**
- **Causa:**
- **Correção:**
