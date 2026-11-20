# 002 — Busca na web: o código decide quando buscar, não o modelo

**Data:** 2026-11-19 · **Status:** aceita · **Revisão:** Antigravity CLI (Gemini 3.8 Flash)

## Problema
Com as ferramentas `buscar_web` e `ler_pagina` disponíveis, o Gemma 4 12B decidia mal quando usá-las. Num teste com 4 perguntas:

| Pergunta | O que ela fez |
|---|---|
| "quem ganhou o último jogo do flamengo?" | Buscou, recebeu só manchetes de pré-jogo e **inventou um placar** ("venceu de virada") |
| "qual a versão mais recente do ollama?" | **Não buscou** e inventou "0.3.12" |
| "o que rolou de notícia sobre a UnB?" | **Não buscou e disse que tinha pesquisado** |
| "diferença entre lista e tupla?" | Não buscou (correto) |

## Tentativas (em ordem)
1. **Aviso no `[contexto]`** ("pesquise antes de responder"): o modelo **ignorou o aviso** na pergunta sobre o Ollama.
2. **Busca forçada pelo código:** uma heurística (`pede_atualidade`) detecta perguntas sobre algo atual, e o núcleo executa a busca antes de chamar o modelo, como se ele tivesse chamado a ferramenta. **Funcionou: passou a buscar em 100% dos casos.**
3. **Ler as páginas automaticamente:** só com título e trecho, ela completava as lacunas. `buscar_web` passou a anexar o texto das 2 primeiras páginas.
4. **Notícias datadas + busca geral:** a busca geral não tem data, e ela tratava página antiga como atual.
5. **Modo thinking** nas perguntas com busca: sem ganho claro, então ficou desligado.

## Escolha
Busca automática decidida pelo código, com o modelo ainda livre pra buscar de novo. Mais as regras na persona: responder só com o que os resultados dizem, dizer de quando é a informação e nunca afirmar que pesquisou sem ter usado a ferramenta.

## Revisão do Antigravity (8 achados)
| Achado | Veredito |
|---|---|
| Busca forçada guardava ~2 mil tokens por busca no histórico | **Aceito:** o histórico guarda só título, link e data (`compactar_ferramenta`) |
| Falsos positivos ("como você está hoje?" disparava busca) | **Aceito:** a heurística passou a usar só termos fortes |
| Texto da web sem delimitação facilita prompt injection | **Aceito:** texto cercado por marcadores que a página não consegue fechar |
| IPv6 `::` passa pelo bloqueio de SSRF | **Rejeitado (testado):** o Python classifica `::` como privado. Investigar revelou outro buraco: `100.64.0.0/10` (faixa da Tailscale) não era bloqueado. **Corrigido**, junto com a restrição às portas 80/443 |
| DNS rebinding | **Aceito como limite conhecido** (veja abaixo) |
| `ddgs` devolve gerador e anula o retry | **Rejeitado (testado):** devolve `list` |
| Erro de rede/HTTP derruba a Athena | **Rejeitado (testado):** `executar()` transforma qualquer exceção em `{"erro": ...}` |
| Argumentos em texto quebram o terminal | **Rejeitado:** o núcleo sempre monta um dicionário |

## Resultado
Ela parou de inventar. Quando a busca falha, diz que não achou. Quando a fonte é antiga, diz a data ("o último jogo que eu encontrei foi em 17/09").

## Limites conhecidos
- **O buscador grátis (DuckDuckGo via `ddgs`) é instável:** às vezes volta vazio e às vezes traz página desatualizada. Mitigações: duas tentativas, depois uma nova busca só com palavras-chave. Próximo passo, se incomodar: Tavily (melhor qualidade, tem plano grátis) ou SearXNG local.
- **DNS rebinding:** `url_permitida` resolve o nome, e o `httpx` resolve de novo ao conectar. Um domínio malicioso com TTL 0 poderia apontar pra rede interna na segunda resolução. Risco baixo pra uso pessoal; a correção (fixar o IP validado na conexão) fica pra antes da Etapa 5, quando existirem ferramentas que alteram o sistema.
- **Heurística em português:** perguntas sobre algo atual que não usam os termos-gatilho não disparam a busca automática. Nesses casos fica por conta do modelo decidir.
