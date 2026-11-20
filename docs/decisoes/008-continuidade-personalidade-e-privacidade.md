# 008 — Continuidade, personalidade e privacidade das buscas (pós-teste no celular)

**Data:** 2026-11-20 · **Status:** aceita (aguardando commit) · **Participantes:** Claude Code (coordenação, implementação), Codex (análise independente; implementou `estado.py` e `memoria.py`), Antigravity (revisor), IBM Bob (auditor de segurança), Gegê (decisões)

## Problema
No teste real pelo celular (madrugada), o Gegê, o Gemini e o ChatGPT apontaram:
- interrogatório (pergunta atrás de pergunta);
- tom de amigo homem dando conselho ("Sinto muito por isso, cara");
- "Quando?" respondido com uma data errada;
- dólar com dois valores diferentes e sem fonte;
- perda de continuidade ("Fiquei doente no dia" não ligado à eleição, e um "ontem" inventado).

## Método: reproduzir antes de mexer
Script com o Gemma real, a mesma conversa de 10 mensagens, relógio fixo às 04h05 (e 21h), pasta de dados temporária e buscas em cache. Variantes isolando hipóteses (sem a linha "ontem", sem "bem curiosa", sem "cara", às 21h, com histórico completo).

### Causas comprovadas
| # | Causa | Evidência |
|---|---|---|
| C1 | Perguntas curtas de seguimento ("Quando?", "tem certeza?") não disparavam a busca: o gatilho só olhava a mensagem atual | 0 de 7 rodadas buscaram |
| C2 | "dólar" fora do gatilho | dólar inventado em várias rodadas; "deixa eu conferir aqui" sem conferir |
| C3 | "quem ganhou as eleições" caía em busca de notícias (por causa do "ganhou"), que olha só a última semana; os resultados não tinham a data de outubro | nem com o histórico **completo** ela acertaria |
| C4 | Sem a informação, ela chutava. A linha fixa "Ontem foi 19/11" e as datas de **publicação** no histórico puxavam o chute | "Quando?" errado em 7 de 7 rodadas; sem a linha "ontem", só mudava qual data errada |
| C5 | O aviso "já foi feita uma busca" era montado **antes** da busca: se ela falhava, o aviso afirmava que havia resultados | `nucleo.py` (achado do Codex) |
| C6 | Falsos positivos: "Você ganhou meu carinho" e "Perdeu minha mensagem?" buscavam notícias | testado (Codex) |
| C7 | A persona ensinava os vícios: "cara" na lista do jeito de falar; exemplos "Ah, cara... Se quiser desabafar", "tô curiosa pra saber por que", "ontem" gratuito, "Olhei aqui e a previsão…" sem busca | as frases do celular seguem esses moldes |
| C8 | Todo "?" dele somava curiosidade **dela**; saturava em 1,0, e o `[contexto]` dizia "bem curiosa com o assunto" o tempo todo | estado real em 0,987 |
| C9 | Clima triste durava 20 min com a instrução "querendo saber o que houve", mesmo quando ele mudava de assunto | diário |
| C10 | O freio de pergunta só olhava o "?" final; ela trocava por pergunta no meio da frase | diário |
| C11 | Privacidade: quem escreve a consulta recebia o **perfil inteiro**, e a consulta vai para a Tavily | achado do Bob |

**Hipótese derrubada:** a compactação do histórico era a causa principal do "Quando?". Não era: a data nunca veio na busca.

## Debate (4 IAs, 2 rodadas, em modo de análise)
| Divergência | Resolução |
|---|---|
| Guardar trechos de página no histórico (Antigravity a favor; Bob contra, por injeção persistente; Codex: medir depois) | **Não guardar.** O teste mostrou que não resolveria, e o risco é real |
| Tirar "Ontem foi…" (Antigravity contra, com argumento falso sobre a 007, depois concordou) | Sai do padrão; entra só quando **ele** fala "ontem"/"anteontem" |
| Freio de pergunta: 2 de 3 (Antigravity) × só a última (Codex) | Só a última, com "?" em qualquer ponto (olhar várias dá aviso falso depois que ela corrigiu) |
| Clima triste: estado novo "acolhido" (Claude) × flag (Antigravity) × cortar (Codex) | Cortado: acolhimento só no turno com tristeza; nos seguintes, o clima só ajusta o humor |
| Cache de busca entre turnos (Antigravity) × só no turno (Codex) | Só no mesmo turno; "tem certeza?" busca de novo de propósito |
| Classificador LLM em toda mensagem | Rejeitado pelos quatro (latência em toda mensagem); reavaliar com dados de uso real |

## Decisões do Gegê
- **Privacidade:** `gerar_consulta` não recebe o perfil; recebe a pergunta, a conversa recente e a âncora. A cidade entra só quando a pergunta depende de lugar. Verificação na saída para o buscador. Bob audita só essa parte.
- **Ordem:** commit da 2.5a e commit do papel do Codex primeiro, separados; estas correções depois, aguardando o "ok".

## O que mudou
| Arquivo | Mudança | Quem |
|---|---|---|
| `athena/prompt.py` | Seguimento (`pergunta_de_seguimento`: curta, interrogativa, não pessoal); cotações com sinal de valor atual; "ganhou/perdeu" só com contexto; tipo de busca por intenção (fato consolidado → geral); "ontem" sob demanda; freio de "?" em qualquer ponto | Claude |
| `athena/nucleo.py` | Âncora = última consulta dos 2 turnos anteriores, lida da memória (`/limpar` apaga); aviso montado **depois** do resultado (`AVISO_BUSCA_FALHOU`); aviso de dado volátil (fonte, horário, modalidade); mesma busca no mesmo turno reaproveitada, se deu certo | Claude |
| `athena/cerebro.py` | `gerar_consulta` sem perfil, system estático (`SYSTEM_CONSULTA`), âncora e cidade na mensagem; Brasil como país padrão; ano que ninguém citou sai da consulta; reserva com a âncora | Claude |
| `athena/ferramentas.py` | `proteger_consulta` dentro de `buscar_web` (vale também para a busca que o modelo chama sozinho): tira nome completo, pares do nome, primeiro nome, apelidos, bairro/endereço e padrões de e-mail/telefone/CPF; passa se ele mesmo pediu; sobrenome sozinho passa ("Marina Silva"). Erro de busca leva "não invente" | Claude |
| `athena/estado.py` | "?" não soma curiosidade; "interessada na conversa"; madrugada não zera o humor; acolhimento só no turno com tristeza, curto, sem "sinto muito"/"tô aqui" | Codex |
| `athena/memoria.py` | Busca no histórico sempre normalizada: `titulo`, `url`, `publicada_em` (data de publicação, não do fato); nunca texto de página | Codex |
| `config/persona.md` | Sem "cara"; carinho como traço ("de vez em quando… sem virar bordão"); exemplos reescritos (menos perguntas, sem "ontem", sem "se quiser desabafar"); exemplo de citar o que a busca trouxe e de dizer que não achou | Claude |
| `config/athena.toml` | "lindão" e "bonito" vigiados contra bordão | Claude |

## Resultados ao vivo (mesmas 10 mensagens, Gemma real)
| Métrica | Antes (3× às 04h05) | Depois (3× às 04h05 + 1× às 21h) |
|---|---|---|
| Respostas terminando em "?" | 4 / 5 / 6 | 4 / 2 / 3 · 3 |
| Total de "?" | 12 / 15 / 12 | 5 / 4 / 4 · 5 |
| "cara" | 4 / 0 / 2 | 0 / 0 / 0 · 0 |
| "ontem" | 3 / 2 / 0 | 0 / 0 / 1* · 0 |
| Fingiu buscar | 0 / 2 / 0 | 0 / 0 / 0 · 0 |
| Buscas na conversa | 2 | 5 (Barcelona, eleições, "Quando?", dólar, "tem certeza?") |
| "Quando?" certo (25/10) | 0 de 7 | **4 de 4** |
| Dólar com fonte e data | nunca | **4 de 4** |

\* "alta de 0,83% em relação a ontem", copiado da fonte (DolarHoje); não é data inventada.

Exemplos depois: "Que fofo, obrigada! Fiquei toda boba agora."; "Ah, não... Que droga. Sobre o dólar, o site DolarHoje.com diz…"; às 21h, "Fico feliz em ser seu remédio de sexta à noite. Só não vale querer me usar pra fugir de tomar o remédio de verdade, hein?". Os jogos do Barcelona continuaram em lista objetiva.

**Uma regressão achada e corrigida no próprio reteste:** sem o perfil, "quem ganhou as eleições" virou "eleições presidenciais EUA 2024" em 2 de 4 rodadas. Corrigido com o Brasil como país padrão no system da consulta (não é dado pessoal) e com a remoção, no código, de ano que ninguém citou. Na segunda bateria: Brasil em 4 de 4.

## Auditoria do Bob (privacidade; 0,58 Bobcoin)
Confirmou: a âncora não carrega texto de página; a barreira fica dentro de `buscar_web` e cobre as buscas que o modelo chama.
| Achado | Veredito |
|---|---|
| E-mail/telefone comparado com o pedido atual por substring | **Aceito:** comparação com fronteira |
| Estado global vazando entre testes se um falhar | **Aceito:** fixture com `monkeypatch` |
| Testes faltando (acento/maiúscula no pedido, e-mail parecido, vazios) | **Aceito** |
| Apelido de 2 letras escapa (limite ≥ 3) | **Rejeitado:** "ge" apagaria o site "ge" de buscas legítimas; o apelido real tem 4 letras |
| A instrução "nunca coloque o nome" é mitigação, não garantia | **Aceito como limite conhecido:** a garantia é `proteger_consulta`, que só conhece o que está no perfil e os padrões |

## Revisão do código
**Antigravity:** a primeira tentativa (diff inteiro, 1.401 linhas) estourou o tempo de 9 min. Ao dividir em duas partes, a cota gratuita acabou ("Individual quota reached", renova em ~6 dias). **A revisão do Antigravity fica pendente** e é feita quando a cota voltar, antes ou depois do commit, conforme o Gegê decidir.

**Codex como revisor independente da parte do Claude** (`nucleo`, `prompt`, `cerebro`, `ferramentas`; ele não escreveu esse código). Foram 10 achados, cada um com evidência executada; os 10 foram confirmados e aceitos:
| Achado | Correção |
|---|---|
| Mencionar um dado pessoal liberava o envio ("Meu nome é Aninha, mas procura a previsão" → "Aninha previsão do tempo") | Só libera se ele **pediu pra pesquisar** aquele termo |
| "Rua Modelo, 123" passava pela vírgula; a busca de reserva recompunha o bairro ao tirar o "de" | Normalização igual nos dois lados, versão sem preposição, proteção reaplicada na consulta simplificada |
| `tipo` malformado vindo do modelo derrubava o turno | `tipo` normalizado antes da chave |
| "Quando chove, fico em casa." disparava busca; "E o horário?" e "Você tem certeza?" não | Exige "?" (ou até 2 palavras); casos incluídos |
| Âncora pegava a primeira busca do lote e ia até pra pergunta completa ("preço do Bitcoin agora?" com âncora "Barcelona") | Última do lote; âncora só se a pergunta depende do assunto |
| "Copa de 2014" ia pra notícias; "notícias das eleições hoje" ia pra geral; "Quem perdeu o carregador?" buscava | Ordem: pedido de notícia → notícias; ano passado/fato consolidado → geral; "quem perdeu" fora |
| "Por que o dólar caiu hoje?" não buscava; "por que a cotação muda?" buscava; "minha bolsa" buscava | Movimento já ocorrido (caiu, subiu…) = fato a verificar; "bolsa" só "bolsa de valores"/B3 |
| Aviso de falha ficava velho se uma nova busca no turno desse certo; resultado vazio sem a observação de falha | Aviso permite usar a nova busca; vazio recebe a observação |
| Filtro de ano deixava "2024," "(2024)" "03/11/2024" e aceitava ano dito só pela Athena | Ano em qualquer token; só autoriza ano dito por ele |
| Teste do "tem certeza?" passava mesmo com cache entre turnos | Teste refeito com a mesma consulta nos dois turnos |

Ressalva: "Sério?" sozinho continua fora do seguimento. É reação emocional mais do que pedido de checagem, e buscar ali seria um falso positivo frequente.

Duas regressões apareceram nos testes durante as correções e foram desfeitas: o "hoje" solto voltaria a mandar "versão do Ollama hoje" pra notícias (erro já apontado pelo Antigravity na 006).

## Limites e pendências
- "Fiquei doente no dia": ela passou a ligar ao dia em que ele ficou triste, mas raramente diz "no dia da eleição". É um limite de correferência do modelo de 12B; medir no uso real.
- O gatilho de seguimento é heurístico: perguntas de seguimento longas ou fora do padrão ainda escapam. Fica para reavaliar com o diário (classificador LLM só se falhar com frequência).
- Mais buscas por conversa (2 → 5) e respostas com busca levando 8–12 s. Todas as buscas a mais foram pedidas pelos casos do teste.
- `proteger_consulta` só conhece os identificadores do perfil e os padrões de e-mail, telefone e CPF.

## Custos
- **Bob:** 0,40 (debate) + 0,26 (rodada 2) + 0,58 (privacidade) = 1,24 Bobcoin. Total do projeto: ~2,3 de 50.
- **Codex:** ~310 mil tokens do plano do Gegê (2 análises de debate, 2 implementações e 1 revisão).

## Números
Testes: 193 → **272**, todos offline. Duas rodadas ao vivo finais, depois da revisão do Codex, confirmaram o comportamento: "Quando?" certo, dólar com fonte e horário, e 3–4 perguntas em 10 mensagens.
