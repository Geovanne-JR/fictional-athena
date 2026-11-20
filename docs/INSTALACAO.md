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

**Busca na web (opcional, recomendado):** crie uma conta grátis em [tavily.com](https://www.tavily.com) e crie um arquivo `.env` na raiz do projeto:
```
TAVILY_API_KEY=tvly-sua-chave
```
Ele fica fora do git. Sem a chave, a Athena usa o DuckDuckGo, que é pior mas funciona.

## 3.1 Limitar o cache do Ollama (evita quedas)
Sem isso, o motor pode cair por falta de RAM em PCs com muitos apps abertos ([decisoes/005](decisoes/005-limite-do-cache-de-prompts.md)):
```powershell
[Environment]::SetEnvironmentVariable("LLAMA_ARG_CACHE_RAM", "2048", "User")
[Environment]::SetEnvironmentVariable("LLAMA_ARG_CTX_CHECKPOINTS", "8", "User")
```
Depois, feche o Ollama pela bandeja do Windows e abra de novo.

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

## 6. No celular (navegador, via Tailscale)
A Athena roda no PC; o celular é só a tela. Funciona fora de casa, no 4G, sem abrir porta no roteador ([decisão 007](decisoes/007-athena-no-celular-pelo-navegador.md)).

1. **Tailscale** no PC (`winget install Tailscale.Tailscale`) e no celular (Play Store), logados na **mesma conta**.
2. No painel do Tailscale (https://login.tailscale.com/admin/dns): ativar **MagicDNS** e **HTTPS Certificates**. Não ative o **Funnel** (ele abre pra internet).
3. Criar a senha do servidor (fica no `.env`, fora do git):
   ```powershell
   .\.venv\Scripts\python -m athena --gerar-token
   ```
4. Subir o servidor e publicar na sua rede (o `serve` é uma vez só; o Tailscale lembra):
   ```powershell
   .\.venv\Scripts\python -m athena --servidor
   & "C:\Program Files\Tailscale	ailscale.exe" serve --bg 8765
   ```
5. No celular, abrir o endereço `https://<nome-do-pc>.<sua-tailnet>.ts.net` que o servidor mostra e digitar o `ATHENA_TOKEN`. Pelo menu do Chrome, "Adicionar à tela inicial" vira um ícone de app.

Terminal e servidor não rodam ao mesmo tempo (uma Athena só, um estado emocional só).

**Se o celular não achar o endereço (`ERR_NAME_NOT_RESOLVED`):** no app do Tailscale, ativar "Use Tailscale DNS" e reconectar; no Android, deixar o "DNS privado" desligado ou automático; no Chrome, desligar o "DNS seguro".

**Para o celular achar o PC, o PC não pode entrar em suspensão** (Configurações → Sistema → Energia).

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
