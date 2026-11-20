# Projeto Olimpo — guia para assistentes de código

Athena 3.0: IA pessoal local (Python 3.11 + Ollama + gemma4:12b-it-qat numa RTX 3060 12GB, Windows 11).
Decisões e roadmap: `docs/ARQUITETURA.md`. Leia antes de propor mudança estrutural.

## Comandos
- Rodar: `.\.venv\Scripts\python -m athena`
- Testes: `.\.venv\Scripts\python -m pytest -q`
- GPU/latência: `.\.venv\Scripts\python scripts\diagnostico.py`

## Regras do projeto
- Código, nomes e comentários em português.
- **Nunca** colocar pesos de modelo (.gguf etc.) dentro do repositório. O Ollama guarda em `%USERPROFILE%\.ollama`.
- **Não usar `llama-cpp-python`** nem CUDA Toolkit: a inferência é sempre via servidor Ollama (`athena/cerebro.py`).
- O system prompt tem que continuar **estático**. Tudo que for dinâmico vai no bloco `[contexto]` (`athena/prompt.py`), senão perde o cache KV.
- `athena/nucleo.py` emite `Evento`s e nunca imprime. Interface fica em `terminal.py` (e futuramente voz/HUD).
- Personalidade se ajusta em `config/persona.md`, não em código. Descreva valores e comportamento; não liste assuntos (o modelo fica obcecado por qualquer tema citado).
- Ferramentas novas: decorator `@ferramenta` em `athena/ferramentas.py`. Ferramenta que altera o sistema precisa de confirmação do usuário.
- `config/perfil.md` e `data/` têm dados pessoais e ficam fora do git.
- Toda lógica nova em estado/memória/prompt ganha teste em `tests/`.
