# Projeto Olimpo — Athena 3.0

IA pessoal 100% local: roda na RTX 3060 via Ollama.

## Usar

```powershell
cd C:\Users\geova\Projeto_Olimpo
.\.venv\Scripts\Activate.ps1
athena                       # ou: python -m athena
athena --modelo qwen3.5:9b   # testar outro cérebro
```

Comandos no chat: `/estado`, `/pensar`, `/metricas`, `/limpar`, `/sair`.

## Instalar do zero (outro PC ou depois de formatar)

1. Driver NVIDIA atualizado. **Não precisa** de CUDA Toolkit: o Ollama traz o dele.
2. `winget install Ollama.Ollama`
3. `ollama pull gemma4:12b-it-qat`
4. Python 3.11+ e então:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python -m pip install -e ".[dev]"
   copy config\perfil.exemplo.md config\perfil.md   # edite com seus dados
   ```
5. `.\.venv\Scripts\python scripts\diagnostico.py`: precisa dizer **100% na GPU**.

## Estrutura

```
athena/          código (núcleo, cérebro, estado emocional, memória, ferramentas)
config/          athena.toml (ajustes), persona.md (personalidade), perfil.md (você)
scripts/         diagnostico.py (GPU + velocidade)
tests/           pytest
docs/            ARQUITETURA.md (decisões + roadmap)
data/            gerado em runtime: estado.json, conversas/*.jsonl (fora do git)
```

Personalidade: edite `config/persona.md`. Ajustes técnicos: `config/athena.toml`. Decisões e próximos passos: [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

Testes: `.\.venv\Scripts\python -m pytest`
