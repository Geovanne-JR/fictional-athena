# Projeto Olimpo — Arquitetura da Athena 3.0

## Visão geral

```
 interface (terminal hoje → voz/HUD depois)
        │  consome Eventos (texto, ferramenta, métricas...)
        ▼
 athena/nucleo.py  ── Athena.responder()
   ├─ estado.py       motor emocional (perceber → decair → descrever)
   ├─ prompt.py       system estático + bloco [contexto] + anti-repetição
   ├─ memoria.py      janela por tokens + diário jsonl
   ├─ ferramentas.py  registro de tools (tool calling)
   └─ cerebro.py      cliente Ollama (streaming, think, tools)
        │ HTTP
        ▼
 Ollama (servidor local, CUDA embutido) → gemma4:12b-it-qat na RTX 3060
```

## Decisões (e o problema da v2.0 que cada uma resolve)

| Decisão | Por quê |
|---|---|
| **Ollama** no lugar de `llama-cpp-python` | Traz o CUDA embutido: sem compilar wheel, sem casar versão de CUDA. A v2.0 carregava DLLs do CUDA 13.2 num PC com 12.4, e a inferência caía na CPU (~40s/resposta). Medido na v3.0: **100% na GPU, ~0,35s até a 1ª palavra, ~31 tok/s**. |
| **Gemma 4 12B QAT** (7,2 GB) | Melhor qualidade por GB que cabe inteiro nos 12 GB com 16k de contexto. Português natural, aceita ferramentas, visão e thinking. QAT = quantizado com treino, perde menos que um Q4 comum. |
| Modelos **fora do projeto** (`%USERPROFILE%\.ollama`) | O `.gguf` dentro de `modelos/` estourava o limite de 20 MB do OpenClaude. |
| **System prompt 100% estático** | Hora, estado e avisos vão num bloco `[contexto]` na mensagem atual. O prefixo não muda, e o Ollama reaproveita o cache KV. |
| **Persona em `config/persona.md`** | Ajustar a personalidade não exige mexer em código. |
| **Persona por valores, não por assuntos** | A v2.0 citava AWS/Flamengo no prompt e o modelo pequeno ficava obcecado nisso. Os gostos do Gegê ficam no `perfil.md` com a regra "só quando for relevante". |
| **Estado emocional contínuo** | Variáveis que sobem e descem com eventos e voltam à base com o tempo. O clima percebido do Gegê decide quanto humor cabe. |
| **Anti-repetição no código** | Detecta aberturas repetidas, respostas que sempre terminam em pergunta e temas puxados sem ninguém pedir, e manda um aviso no `[contexto]`. Regra no prompt sozinha não segura modelo pequeno. |
| **Núcleo emite eventos, não imprime** | Voz e HUD plugam no mesmo `responder()`. |
| **Diário jsonl de tudo** | Matéria-prima da memória de longo prazo (Etapa 3), sem precisar decidir o framework agora. |

## Modelos: alternativas

| Modelo | Tamanho | Quando usar |
|---|---|---|
| `gemma4:12b-it-qat` ✅ padrão | 7,2 GB | Conversa, persona, português |
| `qwen3.5:9b` | 6,6 GB | Mais leve; forte em ferramentas e código. Ainda não comparado: `python scripts/diagnostico.py --modelo gemma4:12b-it-qat --modelo qwen3.5:9b` |
| `gemma4:26b-a4b-it-qat` | 16 GB | "Modo pesado": não cabe na VRAM, parte vai pra RAM (MoE com ~4B ativos, então ainda é usável). Não testado. |

Troca rápida: `athena --modelo qwen3.5:9b`.

## Orçamento de VRAM (12 GB)

| Item | VRAM |
|---|---|
| Windows + apps (Lively, Edge, Steam...) | ~1,7 GB |
| Gemma 4 12B + 16k de contexto | ~8,3 GB |
| **Sobra** | **~2 GB** |

Isso decide a Etapa 4: o Whisper `large-v3-turbo` int8 (~1,5 GB) cabe apertado. Se não couber, roda na CPU (o Ryzen 5600 aguenta o `small`/`turbo`). O Piper TTS roda na CPU. O `keep_alive = "20m"` tira o modelo da VRAM quando você vai jogar.

## Roadmap

### Etapa 1 — Cérebro e persona ✅ (v3.0)
Feito: Ollama, Gemma 4, persona nova, motor emocional, anti-repetição, memória por tokens, diário, tool calling (`status_do_pc`), diagnóstico de GPU, testes.
Próximo ajuste fino: conversar bastante, ler `data/conversas/*.jsonl` e calibrar `persona.md` e os pesos de `estado.py`.

### Etapa 2 — Internet
- Ferramenta `buscar_web` com `ddgs` (DuckDuckGo, sem chave) + `trafilatura` pra extrair o texto das páginas.
- Se a qualidade for fraca: Tavily (tem plano grátis, retorna texto já limpo).
- Regra na persona: fato recente → buscar antes de responder, citar a fonte.

### Etapa 3 — Memória de longo prazo
- Embeddings locais via Ollama (`embeddinggemma` ou `bge-m3`, ambos multilíngues).
- Vetores em ChromaDB, em 3 coleções (as antigas "salas"): **fatos** sobre o Gegê, **episódios** (resumos do diário) e **documentos** (PDFs da UnB).
- Ao fim da sessão, o próprio modelo extrai fatos e preferências do diário. Recuperação: top-k relevante entra no `[contexto]`.
- Mem0 (OSS, roda com Ollama + Chroma) é a alternativa pronta se a versão própria der trabalho. Zep exige servidor e banco de grafos, o que é demais pra um PC só.

### Etapa 4 — Voz
- Ouvir: `faster-whisper` + VAD (silero) + palavra de ativação (`openWakeWord`).
- Falar: Piper TTS (voz pt_BR, local, rápido). O Edge-TTS soa melhor, mas é nuvem (opcional).
- Falar frase a frase enquanto o modelo ainda gera, pra latência percebida ficar abaixo de 1s.

### Etapa 5 — Controle do PC + HUD
- Leitura (já começou): psutil + nvidia-smi. Temperatura da CPU e ventoinhas: LibreHardwareMonitor (expõe JSON/WMI).
- Ventoinhas: o Python não controla direto no Windows. O caminho é o app FanControl com perfis, e a Athena só troca de perfil.
- Ações (abrir programa, volume, scripts): ferramentas marcadas como **ação** pedem confirmação antes de executar. Nunca rodar comando arbitrário vindo do modelo.
- HUD: FastAPI + WebSocket servindo uma página com um "orb"/avatar que reage aos Eventos do núcleo (pensando, falando, humor). Depois dá pra empacotar com Tauri.
