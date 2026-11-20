# 003 — Tavily como buscador principal, DuckDuckGo de reserva

**Data:** 2026-11-19 · **Status:** aceita · **Revisão:** Antigravity CLI (Gemini 3.8 Flash)

## Problema
Com o DuckDuckGo (`ddgs`), a busca automática ([002](002-busca-web-automatica.md)) deixou a Athena honesta, mas pouco útil: a biblioteca não é oficial, volta vazia com frequência e traz páginas sem data e desatualizadas.

## Opções (planos grátis em nov/2026)
| Opção | Grátis? | Observação |
|---|---|---|
| **Tavily** | 1.000 créditos/mês, sem cartão | API oficial, notícias com data de publicação, filtro de período, já devolve o texto das páginas |
| Brave Search | US$ 5/mês de crédito, **exige cartão** | Removeu o plano grátis em fev/2026 |
| Busca do Ollama | Grátis com conta | Limite do plano grátis não publicado |
| SearXNG local | Grátis | Exige Docker e continua raspando outros buscadores |

## Escolha
Tavily como principal. O DuckDuckGo fica de reserva, usado automaticamente sem chave, sem créditos ou se a Tavily cair. A chave fica em `.env`, fora do git.

## O que mais precisou mudar
Só trocar o buscador não bastou. Mesmas 3 perguntas em cada rodada:

| Rodada | Flamengo (jogo de ontem) | Ollama (0.40.16) | UnB (notícias da semana) |
|---|---|---|---|
| DuckDuckGo | Jogo antigo (setembro) | Página velha (0.40.5) | ✅ |
| Tavily, pergunta crua | Jogo antigo | ✅ | ❌ University of New Brunswick (Canadá) |
| Tavily + **consulta escrita pelo modelo** + notícias da **semana** | ✅ 2×1 Athletico-PR, com os gols | ❌ 0.40.9 (consulta com "resultado") | ✅ |
| Ajuste do prompt da consulta, sem filtro de país | ✅ | ✅ | ✅ |

1. **O modelo escreve a consulta.** O código continua decidindo *quando* buscar ([002](002-busca-web-automatica.md)), mas a pergunta crua é uma consulta ruim. `Cerebro.gerar_consulta` usa o perfil do usuário pra expandir siglas ("UnB" vira "Universidade de Brasília"). Custa menos de 1s.
2. **Notícias: primeiro a última semana**, e o mês só se vier vazio. Com "mês", a eliminação na Libertadores (muito noticiada) abafava o jogo de ontem.
3. **Sem filtro de país:** `country=brazil` atrapalhava assunto técnico, e o contexto do Brasil agora vem da consulta.

## Revisão do Antigravity (6 achados)
| Achado | Veredito |
|---|---|
| Texto das páginas atribuído antes de ordenar por data | **Aceito (bug real):** as notícias mais novas ficavam sem texto |
| Preâmbulo do modelo ("Aqui está a consulta:") viraria a consulta | **Aceito:** `extrair_consulta` pula preâmbulo, cercas, `<think>` e aspas |
| Comentário na mesma linha do `.env` corromperia a chave | **Aceito** |
| Sem `perfil.md` a Athena quebra | **Rejeitado:** `config.py` já cai pro `perfil.exemplo.md` |
| `include_raw_content: "text"` dá HTTP 422 | **Rejeitado (testado):** a API real devolve 200 com o texto |
| Semana vazia → mês gasta 2 créditos | **Rejeitado:** só acontece com a semana vazia, e ampliar vale o crédito |

## Também nesta mudança
Os testes leram a chave real do `.env` e chamaram a Tavily pela internet. O `tests/conftest.py` agora isola o ambiente: nenhum teste usa a chave real nem gasta créditos.

## Custo
~1 crédito por busca (2 quando a semana vem vazia). Uso estimado: 300 a 600 por mês, dentro dos 1.000 grátis. Quando acabarem, ela cai sozinha pro DuckDuckGo.
