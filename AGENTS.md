# Projeto Olimpo — regras para assistentes de IA

Fonte única de regras para todas as IAs que trabalham neste repositório (Claude Code, Antigravity/Gemini e outras).
`CLAUDE.md` só aponta para este arquivo.

Athena 3.0: IA pessoal local (Python 3.11 + Ollama + gemma4:12b-it-qat numa RTX 3060 12GB, Windows 11).
Decisões e roadmap: `docs/ARQUITETURA.md`. Leia antes de propor mudança estrutural.

## Papéis
O dono do projeto (Gegê) toma todas as decisões finais. Nenhuma IA muda o rumo da arquitetura sozinha.

| IA | Papel | Pode editar arquivos? |
|---|---|---|
| Claude Code | Arquiteto e implementação; mantém `docs/ARQUITETURA.md` | Sim |
| Antigravity CLI / Gemini | Revisor: revisa cada entrega (bugs, riscos, alternativas) | **Não**, a menos que o Gegê peça explicitamente naquela conversa |
| IBM Bob (Bob Shell) | Auditor: auditoria de segurança e qualidade nos marcos do projeto (fim de etapa, antes de ferramentas que alteram o sistema) | **Não**, a menos que o Gegê peça explicitamente naquela conversa |

Revisor e auditor: trabalhem em modo somente leitura (`plan` no Antigravity, `ask` no Bob). Entreguem os achados como lista (arquivo:linha, problema, por que importa, sugestão). Discordar da arquitetura é bem-vindo, mas com argumento, não com reescrita. Quem implementa testa cada achado antes de aceitar; os rejeitados são registrados com o motivo em `docs/decisoes/`.

O Bob roda num teste com créditos limitados (Bobcoins): auditorias focadas num diff ou numa área, nunca "revise o repositório inteiro".

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
- A Athena libera a VRAM ao sair/despedir (`Athena.dormir()`); não reintroduzir `keep_alive` longo.
- `config/perfil.md` e `data/` têm dados pessoais e ficam fora do git.
- Toda lógica nova em estado/memória/prompt ganha teste em `tests/`.
- Decisão importante de arquitetura ganha um registro em `docs/decisoes/` (problema, opções, escolha, porquê). É material pro TCC.
