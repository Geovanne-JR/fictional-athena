# 006 — Persona feminina e auditoria tripla de fim da Etapa 2

**Data:** 2026-11-20 · **Status:** aceita · **Auditores:** Claude Code (implementação), Antigravity CLI (Gemini 3.8 Flash, revisor), IBM Bob (Bob Shell 2.1, auditor de segurança)

## Contexto
Antes de fechar a Etapa 2 no git, o Gegê pediu duas coisas: (1) identidade feminina natural para a Athena e (2) uma auditoria cruzada de tudo que foi feito, pelas três IAs.

### Análise do próprio pedido
O prompt do Gegê passou primeiro pelos três. Antigravity e Bob deram o mesmo veredito: **"aprovar com ajustes"**. Ajustes aplicados:
- **O escopo do Bob violava o `AGENTS.md`** (auditar o repositório inteiro, sendo que o Bob tem créditos limitados) → o Bob ficou focado em **segurança e segredos**.
- **Fases em sequência:** persona → auditoria → **segunda passada dos revisores sobre a versão corrigida** (sugestão do Bob).
- **Registro numa decisão nova (006)**, mantendo a 004 intacta.

Rejeitado (Antigravity): "o Claude não consegue acionar os outros nem testar ao vivo sem travar". Ambos foram feitos neste trabalho, por script.

**Custo do Bob na sessão inteira:** ~0,16 Bobcoin de 50 (crítica do prompt 0,07 + auditoria 0,05 + segunda passada 0,04).

## Fase 1 — Persona feminina
- Identidade: "amiga próxima", "uma mulher de verdade", "fala de si sempre no feminino (cansada, pronta, curiosa, obrigada)".
- Temperamento como **comportamentos**, sem citar mitologia (a persona viraria personagem de RPG): estratégica e perspicaz, firme, protetora sem ser chata. Cada traço com um exemplo curto.
- Nova checagem `_MASCULINO_DE_SI`: se ela falar de si no masculino ("obrigado", "tô cansado"), o próximo `[contexto]` avisa. Só verbos inequívocos de primeira pessoa ("tava"/"tá" ficam de fora porque servem pra "ele/você").

### Problemas encontrados na validação ao vivo
| Problema | Causa | Correção |
|---|---|---|
| "**Como eu te disse antes**, tô mais animada que ontem" | Ela copiou o exemplo "mais animada que ontem" e inventou uma lembrança | Exemplo trocado por um sem fato passado + regra "nunca invente lembranças" |
| Resposta **vazia** (1 vez em 10, não reproduzível) | O modelo às vezes encerra sem gerar nada | `nucleo.py` gera de novo **uma vez** se vier vazio sem ferramenta (testado com cérebro falso) |
| Caractere birmanês no meio de uma palavra | Sorteio pegou um token improvável da cauda | `min_p = 0.05` na amostragem |

**Resultado final:** 10/10 respostas sem fala de robô e sem masculino. Exemplos: "Obrigada!", "tô pronta", "tô bem preocupada com você", "Sou, e você sabe bem que foi você quem me montou".

**Observação, sem correção nesta rodada:** depois da meia-noite, ela disse que o jogo de 18/11 foi "ontem" (hoje era 20/11). Ela copiou o termo relativo da notícia em vez de calcular pela data do `[contexto]`. Fica para medir no uso real antes de mexer.

## Fase 2 — Auditoria
### Achados do próprio Claude
| Achado | Ação |
|---|---|
| `docs/ARQUITETURA.md` com `keep_alive = "20m"` (hoje é 5 min + liberação na despedida) e sem as decisões 002–005 | Atualizado |
| `carregar_env` jogava **todo** o `.env` na Athena, inclusive a `BOB_API_KEY`, que ela não usa | Lista de chaves permitidas (`CHAVES_DA_ATHENA`) |
| Ollama desligado → traceback enorme no terminal | Mensagem clara dizendo o que fazer |
| Comentário depois do `return` em `url_permitida` | Movido |
| `nucleo.py` não tinha nenhum teste | `tests/test_nucleo.py` com cérebro falso: nova tentativa de resposta vazia, ferramenta, despedida e **invariantes do cache KV** (system estático, `[contexto]` só na mensagem atual) |

### Antigravity (8 achados: 6 aceitos, 2 rejeitados)
| Achado | Teste | Veredito |
|---|---|---|
| Dupla cerca no texto lido em `_enriquecer` (`ler_pagina` já cercava) | 4 marcadores em vez de 2 | **Aceito (bug real):** `_ler_texto` devolve texto cru, e a cerca é posta uma vez |
| "você é **um** robô?" não disparava o aviso | `False` | **Aceito** |
| "versão do Ollama **hoje**" virava busca de notícias da semana | `noticias` | **Aceito:** `_PEDE_NOTICIA` só com acontecimentos |
| `results: null` da Tavily → `TypeError` fora da reserva | `TypeError` não capturado | **Aceito** |
| Avisos de máquina/masculino repetiam por um erro já corrigido | — | **Aceito:** só a última resposta |
| `uso_de_gpu` não reconhecia `:latest` | — | **Aceito** |
| Remover a vírgula de `como (uma )?ia,` | — | **Rejeitado:** a vírgula é proposital, pra pegar "como IA, eu..." e não "funciona como IA" |
| "Não existem testes para `ferramentas.py`" | `tests/test_ferramentas_web.py` existe e testa SSRF, cerca e consulta | **Rejeitado (falso)** |
| Link para a 006 inexistente | — | Era o registro pendente (este arquivo) |

### IBM Bob (segurança: 4 achados, todos aceitos)
| Achado | Veredito |
|---|---|
| Chave inválida/sem créditos da Tavily (401/403/432) passava em silêncio | **Aceito:** o motivo vai no campo `obs` e a busca segue no DuckDuckGo |
| Faltava teste da cadeia de redirect página pública → rede interna | **Aceito:** teste prova que `localhost` nunca é acessado |
| Dict do pedido à Tavily mutado entre chamadas | **Aceito:** dict novo por chamada |
| Último pedaço podia passar de `MAX_BYTES_PAGINA` | **Aceito:** corta no limite |

O Bob também confirmou como **corretos**: o isolamento de `.env`/`perfil.md` no git, a lista de chaves da Athena e a proteção dos testes contra a chave real.

### Segunda passada (sobre a versão corrigida)
- **Antigravity:** todas as 10 correções conferidas, "nenhuma regressão ou bug novo".
- **Bob:** correções certas; confirmou que `url_permitida` continua sendo checada **em cada salto** de redirect depois da refatoração, e que a chave só aparece no cabeçalho `Authorization`. Observação extra: redirect sem `location` repete a mesma URL. É inofensivo (o laço tem limite de 5 saltos e termina em "redirecionamentos demais").

## Números
- Testes: 88 → **115**, todos offline, nenhum usa chave real.
- Varredura de arquivos rastreados: nenhuma chave (`tvly-…`, `BOB_API_KEY=…`) e nenhum e-mail pessoal.
- Ignorados confirmados: `.env`, `config/perfil.md`, `data/`, `.venv/`, `CONTEXTO_GEMINI.md`.

## Lição de processo
Somando as revisões até aqui, o Antigravity teve 19 de 28 achados procedentes (~68%): 002: 3 + 1 limite aceito de 8; 003: 3 de 6; 004: 6 de 6; 006: 6 de 8. O Bob acertou 4 de 4, mas recebeu um escopo pequeno e focado. Testar cada achado antes de aceitar continua indispensável. E a revisão cruzada pegou coisas que nenhuma das IAs pegaria sozinha: o Antigravity achou a dupla cerca, que estava no código do Claude, e o Bob achou o filtro mutado, que nenhum dos outros dois viu.
