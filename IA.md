# Registro de uso de IA

Ferramenta: Claude (Anthropic), usado para comparar os artigos com o projeto da
equipe, escrever o código da miniatura e da análise e revisar o texto.

Tudo o que o laudo relata como observado vem das execuções da equipe, guardadas
em `logs/`. A rodada 1 (`logs/*_r1`) foi rodada pela equipe no Docker, em
Linux. A rodada 2 foi rodada no Docker Desktop do Windows, na máquina de Giulia,
pelo Claude Code a pedido dela, para conferir se o passo a passo do README
funciona em outro sistema. Foi essa conferência que revelou o Erro 2. Os testes
locais que a IA fez antes, sem Docker, **não** fazem parte do repositório.

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
- **Observação:** o erro apareceu ao rodar o código da análise antes da primeira
  execução no Docker. Com a correção, `logs/validacao_r1/resumo.md` mostra
  "sem falha", como esperado.

### Erro 2: o cliente começava depois do incidente no Docker Desktop do Windows

- **Onde:** `docker-compose.yml`, ordem de subida do `injetor` e do `cliente`.
- **Como apareceu:** ao rodar o README no Windows (Docker Desktop), o
  `sem_backoff` deu só 0,3 % de erro e "recuperou antes da intervenção", o
  contrário da rodada 1 em Linux (40,4 %). Em `cliente_eventos.csv`, o cliente
  só começou 56 s depois da política em branco no `sem_backoff` e 101 s depois
  no `jitter`, quando o red-button (t = 20 s) e até a intervenção (t = 80 s) já
  tinham passado. Essas execuções estão guardadas em `logs/invalidas_windows/`
  e não entram no laudo nem em `logs/comparacao.md`.
- **Causa:** o `injetor` dependia só do `politicas` e começava a contar o
  roteiro assim que o banco subia. O `cliente` dependia do `controle` e
  esperava as 30 réplicas serem criadas, o que no Windows demora muito mais.
  A IA supôs que todos os containers subiriam juntos; em Linux a diferença era
  pequena e o erro não aparecia.
- **Correção:** `depends_on: [politicas, cliente]` no `injetor`, para o roteiro
  só começar com a carga já rodando. Rodamos de novo os 3 cenários no Windows
  (`logs/*_r2`). Agora o cliente começa cerca de 31 s antes da política em
  branco (`cliente_eventos.csv`), e o resultado reproduz o da rodada 1: sem
  backoff, falha em 3 s e só volta depois da intervenção (72,0 s); com jitter,
  volta sozinho em 16,8 s; com validação, nada falha (`logs/comparacao.md`).
