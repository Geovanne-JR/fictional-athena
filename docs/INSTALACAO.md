# Instalação

Testado no Windows 11 com RTX 3060 12GB, Ryzen 5 5600 e 32GB de RAM.

## 1. Pré-requisitos
- Driver NVIDIA atualizado. **Não precisa** de CUDA Toolkit: o Ollama traz o runtime CUDA dele.
- [Ollama](https://ollama.com): `winget install Ollama.Ollama`
- Python 3.11 ou mais novo

## 2. Modelo
```powershell
ollama pull gemma4:12b-it-qat
```
O modelo fica guardado em `%USERPROFILE%\.ollama`, fora do projeto.

## 3. Projeto
```powershell
git clone https://github.com/Geovanne-JR/fictional-athena.git
cd fictional-athena
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
copy config\perfil.exemplo.md config\perfil.md
```
Edite o `config/perfil.md` com quem você é. Ele fica fora do git.

## 4. Diagnóstico
```powershell
.\.venv\Scripts\python scripts\diagnostico.py
```
O resultado precisa dizer **100% na GPU**. Se não disser, feche os apps que usam VRAM (wallpaper animado, jogos, navegador), reduza o `num_ctx` em `config/athena.toml` ou use um modelo menor.

Pra comparar modelos:
```powershell
.\.venv\Scripts\python scripts\diagnostico.py --modelo gemma4:12b-it-qat --modelo qwen3.5:9b
```

## 5. Usar
```powershell
.\.venv\Scripts\Activate.ps1
athena                        # ou: python -m athena
athena --modelo qwen3.5:9b    # outro cérebro
athena --sem-ferramentas
```

Comandos no chat:

| Comando | O que faz |
|---|---|
| `/estado` | mostra o estado emocional interno |
| `/pensar` | liga/desliga o raciocínio estendido |
| `/metricas` | mostra/esconde a latência e os tokens/s |
| `/limpar` | esquece a conversa atual |
| `/sair` | encerra |

## Onde ficam as coisas
| Caminho | Conteúdo |
|---|---|
| `config/athena.toml` | modelo, contexto e amostragem |
| `config/persona.md` | personalidade |
| `config/perfil.md` | quem é o usuário (privado) |
| `data/estado.json` | estado emocional persistido |
| `data/conversas/*.jsonl` | diário de todas as conversas (privado) |

## Testes
```powershell
.\.venv\Scripts\python -m pytest -q
```
