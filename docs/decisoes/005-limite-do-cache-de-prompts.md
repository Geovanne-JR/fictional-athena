# 005 — Limitar o cache de prompts do llama-server (quedas por falta de memória)

**Data:** 2026-11-19 · **Status:** aceita

## Problema
Durante os testes, o motor do Ollama caiu duas vezes no meio de uma resposta (`error reading llama-server response`, HTTP 500). Log do servidor (`%LOCALAPPDATA%\Ollama\server.log`):

```
srv  alloc: failed to allocate memory for prompt cache state: std::bad_alloc
llama-server terminated ... exit status 0xc0000409
```

O Ollama 0.40 usa o `llama-server` do llama.cpp, que guarda um **cache de prompts na RAM** (padrão 8 GB) e até **32 checkpoints de contexto** por conversa (~320 MB cada no Gemma 4, por causa da atenção com janela deslizante). O cache chegou a 3,2 GB num PC com muitos apps abertos, e a alocação falhou. A chamada extra de `gerar_consulta` ([003](003-tavily-como-buscador-principal.md)) aumenta o número de prompts em cache.

## Escolha
Variáveis de ambiente do usuário, que o `llama-server` herda do Ollama:

```
LLAMA_ARG_CACHE_RAM=2048       # cache de prompts: 8 GB → 2 GB
LLAMA_ARG_CTX_CHECKPOINTS=8    # checkpoints: 32 → 8
```

Depois disso, o log mostra `limits: 2048.000 MiB`, e as mesmas conversas rodaram sem queda (o cache passou de 1,9 GB e foi aparado em vez de estourar).

## Consequências
- Menos prompts guardados = um pouco mais de reprocessamento em conversas longas. Não foi perceptível nos testes.
- A configuração fica **na máquina, não no repositório**. Numa instalação nova, é preciso definir as variáveis (veja `docs/INSTALACAO.md`) e reiniciar o Ollama.
- Para desfazer: apagar as duas variáveis do usuário e reiniciar o Ollama.
