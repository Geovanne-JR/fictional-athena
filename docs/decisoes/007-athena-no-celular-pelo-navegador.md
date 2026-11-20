# 007 — Athena no celular pelo navegador (Etapa 2.5a) e datas relativas

**Data:** 2026-11-20 · **Status:** aceita · **Revisão:** Antigravity CLI (debate + revisão do código), IBM Bob (debate + auditoria de segurança)

## 1. Ordem do roadmap
**Problema:** o plano era servidor → app Kotlin → memória. O app nativo exige Android Studio e só se paga com voz (rodar em segundo plano, botão do fone, assistente padrão).

**Opções:** (a) 2.5a servidor → 2.5b app Kotlin → 3 memória; (b) 2.5a servidor → 3 memória → 2.5b app Kotlin junto com a Etapa 4 (voz); (c) memória antes de tudo.

**Escolha: (b).** Proposta original do Claude era (a). O Antigravity discordou: um app nativo só para texto seria refeito quando a voz chegasse. O Bob aceitou as duas ordens e preferiu (b). O Claude mudou de posição. (c) foi descartada porque o diário tinha **1 arquivo**: sem uso real não há o que lembrar, e a página no celular é o que gera uso. O servidor também define o ciclo de sessão, de que a memória depende.

**Custo do debate:** Bob 0,24 Bobcoin.

## 2. Servidor
| Decisão | Por quê |
|---|---|
| **WebSocket** (não SSE) | bidirecional: ping, e o app Kotlin (OkHttp) usa direto |
| Núcleo **numa thread**; a thread libera a trava no `finally` | o núcleo é síncrono e travaria o servidor; se o celular cair no meio, a resposta termina e fica na memória (os dois revisores) |
| **Uma resposta por vez** (`ocupada` imediato, sem fila) | uma Athena, uma GPU (Bob) |
| **Trava de instância** (`data/athena.lock`) | terminal e servidor juntos sobrescreveriam o `estado.json` um do outro |
| Escuta **só em 127.0.0.1**; o **Tailscale Serve** publica com HTTPS **só na tailnet** (Funnel desligado) | bind no IP 100.x quebra se o Tailscale não subiu (Antigravity); HTTPS é exigido pelo cookie `Secure` e pela instalação como app (Bob) |
| VRAM: só por **inatividade** (`keep_alive` 5 min, já em toda chamada) ou **despedida** | liberar a cada queda de conexão faria recarregar o modelo toda vez que a tela do celular apaga (Antigravity) |
| **Sessão expira** após 30 min parada (memória curta zera; emoção continua) | com o servidor sempre ligado, a conversa nunca zeraria (Antigravity) |
| API (`/api/*`, `/ws`) separada da página | o app Kotlin vai consumir a mesma API com `Authorization: Bearer` |

### Segurança
- `ATHENA_TOKEN` no `.env` (192 bits, `--gerar-token`). O navegador troca o token por um **cookie HttpOnly + Secure + SameSite=Strict**, derivado por HMAC (trocar o token invalida os cookies).
- **Token nunca na URL** (vaza em log e histórico; os dois revisores). O Bob sugeriu token em cabeçalho no WebSocket: **rejeitado**, a API de WebSocket do navegador não permite cabeçalhos. Solução: cookie.
- WebSocket: **Origin e login checados antes do `accept`** (Bob).
- `TrustedHostMiddleware` com **hosts exatos** (o nome `.ts.net` deste PC é lido do Tailscale e validado). Nada de `*.ts.net`: aceitaria páginas de outras máquinas e de Funnels alheios.
- Página: CSP sem `unsafe-inline`, arquivos de lista fechada (sem servir pasta), texto dela **só via `textContent`** (texto da web pode trazer HTML).
- Sem `/docs` nem `/openapi.json`. Erro genérico para o cliente; detalhe só no log.

## 3. Datas relativas ("ontem")
**Problema (registrado na 006):** depois da meia-noite ela disse "ontem" para um jogo de dois dias antes. Ela copiava o termo da notícia.

**Correção:** o código faz a conta. O `[contexto]` diz qual foi ontem; cada resultado datado ganha `publicada: "anteontem (quarta-feira, 18/11)"`, com uma nota explicando que a data do fato está no texto.

**Dois bugs achados no teste ao vivo, depois da primeira versão:**
1. **Fuso horário:** a data de publicação era lida em GMT. "Thu, 19 Nov 01:27 GMT" é 22h27 de **18/11** em Brasília. Corrigido para o fuso do PC (testes fixam -03:00).
2. **Nome do campo:** a primeira versão chamava o campo de `quando`, e ela leu como a data do jogo ("foi em 19/11", publicação). Renomeado para `publicada`. Resultado ao vivo: *"O jogo foi na quarta-feira, dia 18."*

Também ao vivo: "e quando é o próximo jogo?" não disparava a busca e ela **fingiu que pesquisou** ("deixa eu ver aqui..."). `_PEDE_ATUALIDADE` ganhou "próximo jogo/episódio/…" e "quando … joga/estreia".

## 4. Revisões do código
### IBM Bob (segurança; 0,50 Bobcoin) — nenhum achado crítico ou alto
| Achado | Teste | Veredito |
|---|---|---|
| CSP montado com o Host antes do `TrustedHost` validar | Host `malicioso.com` aparecia no cabeçalho do 400 | **Aceito** |
| Frame de WebSocket até 16 MB (padrão do uvicorn) | confirmado | **Aceito:** `ws_max_size` 64 KB |
| Nome do Tailscale entra na lista sem validação | — | **Aceito:** regex `*.*.ts.net` exato |
| Faltava teste de 401 no `/api/limpar` | — | **Aceito** |
| Aviso "use o nome, não o IP" | — | **Aceito** |
| `/api/sair` sem login = CSRF de logout | O Origin já é checado, e apagar o cookie só afeta quem fez o pedido | **Rejeitado** |
| `asyncio.Queue` sem limite | A resposta é limitada pelo `num_ctx`; com limite, tokens seriam descartados | **Rejeitado** |

### Antigravity (9 achados: 8 aceitos, 1 em parte)
| Achado | Teste | Veredito |
|---|---|---|
| Aquecer e responder ao mesmo tempo no Ollama | os testes usavam `aquecer=False` | **Aceito:** a resposta espera o aquecimento |
| Histórico mostrava conversa já expirada | — | **Aceito:** `expirar_se_parada()` também no histórico |
| Celular reconectando no meio de uma resposta ficava preso em "terminando" | — | **Aceito:** toda reconexão redesenha pelo histórico e consulta até terminar |
| DuckDuckGo sem o fuso (e ISO com `Z`/`+00:00` cortado cru) | `2026-11-19T01:27:52+00:00` → `19` | **Aceito** |
| Rótulo sem o ano ("há 24 meses (…, 20/11)") | confirmado | **Aceito:** ano quando não é o atual, e "há 2 anos" |
| "quando o Flamengo joga?" não buscava | `False` | **Aceito** |
| `delete_cookie` sem as flags | — | **Aceito** (higiene) |
| Sem `try/finally` liberando a VRAM | — | **Aceito** |
| Leitura do histórico concorrente "lança RuntimeError" | Lista não lança isso (só dict/set); pode ver estado parcial | **Em parte:** lê de uma cópia |

### Lição
O teste ao vivo pegou o que 159 testes offline não pegaram: o uvicorn sem a biblioteca `websockets` recusava o `/ws`, porque o `TestClient` não usa o uvicorn. Agora há um teste para isso. E a correção do "ontem" criou um erro novo (data de publicação lida como data do fato), que só apareceu perguntando de verdade.

## 5. Teste do Gegê no celular (Poco F7 Ultra, 5G, fora do Wi-Fi)
**Funcionou:** login, streaming com **0,4–0,5s** até a 1ª palavra, busca na web e despedida liberando a GPU. Um tropeço de configuração: o celular não resolvia o nome `.ts.net` até o MagicDNS ser ativado no app (registrado no `INSTALACAO.md`).

**Problemas de comportamento que ele apontou** (do núcleo, não do servidor):
| Problema | Causa (pelo diário) | Correção |
|---|---|---|
| "Quando foi as eleições?": data inventada e repetida | não disparava a busca | gatilho ampliado, ancorado em evento ("quando foi/é **o jogo/a eleição**…") |
| "Vai ter jogo do Barcelona?": "deixa eu ver aqui…" sem buscar | não disparava a busca; ela fingiu que pesquisou | idem |
| "Data do próximo jogo?" depois de Barcelona virou Flamengo x Palmeiras | quem escreve a consulta só via a frase atual + o perfil (time dele) | `gerar_consulta` recebe as últimas mensagens dele e a última dela |
| 4 de 5 respostas terminando com pergunta | o aviso só vinha após duas seguidas | aviso logo após uma |
| Consulta "eleições 2022" em 2026 (visto no reteste) | o modelo pôs um ano do treinamento | "não use anos do treinamento; use o atual ou o que ele disse" |

### Revisão do Antigravity sobre esses ajustes (7 achados)
Aceitos 6: fallback da consulta devolvia o texto com a conversa (bug real); anotação de teste no prompt ancorava em 2022; a consulta não via a resposta dela; o aviso de pergunta podia ser falso; falsos positivos ("jogo da velha", "deadlock", "eleição de líder no Raft") e negativos ("quando foram", "quando é o jogo").
**Rejeitado depois de testar ao vivo:** buscar eleições como **notícia**. O filtro da última semana trouxe só notícias de prestação de contas, sem a data de uma eleição de outubro. Com a busca geral veio o TSE: "4 de outubro de 2026".

**Reteste ao vivo com as mesmas perguntas:** as três buscam; Barcelona continua Barcelona (ela separou basquete, futebol e futsal e perguntou qual); eleições respondidas certo (4/10 e 25/10/2026); perguntas no fim de 4 em 5 para 1 em 5.

**Limites que ficam:** "Barcelona" é ambíguo e a busca de notícias mistura times; ela às vezes promete "vou tentar de outro jeito" e não busca de novo. Para medir no uso real.

## Números
Testes: 115 → **193**, todos offline. Bob na sessão: 0,24 (debate) + 0,50 (auditoria).
