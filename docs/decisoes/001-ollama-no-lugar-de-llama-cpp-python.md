# 001 — Ollama no lugar de llama-cpp-python

**Data:** 2026-11-19 · **Status:** aceita

## Problema
A Athena v2.0 levava ~40s por resposta curta numa RTX 3060, mesmo com `n_gpu_layers=-1`. O script carregava as DLLs do CUDA 13.2, mas a máquina tinha o CUDA Toolkit 12.4, e a wheel do `llama-cpp-python` era compilada pra outra versão. A inferência caía na CPU sem nenhum aviso. Compilar a wheel com CUDA no Windows também tinha falhado no Python 3.13.

## Opções
1. **Consertar o `llama-cpp-python`**: casar a versão da wheel com o CUDA instalado. Frágil: quebra de novo a cada atualização de driver, CUDA ou Python.
2. **`llama.cpp` puro (servidor `llama-server`)**: binário pronto com CUDA, rápido e com controle total. Mas exige gerenciar downloads de modelos, templates de chat e flags na mão.
3. **Ollama**: servidor local que embute o runtime CUDA, baixa modelos com um comando e expõe API com streaming, tool calling e "thinking". Usa o llama.cpp por baixo.

## Escolha
**Ollama**, com a Athena falando com ele por HTTP (`athena/cerebro.py`).

## Por quê
- Elimina a classe inteira de problemas de compilação e versão de CUDA: não precisa nem do CUDA Toolkit instalado.
- Separa o cérebro do programa: o modelo pode ficar quente na VRAM entre execuções, e trocar de modelo é trocar uma string.
- O desempenho é o mesmo do llama.cpp, que roda por baixo.

## Resultado medido (RTX 3060 12GB, gemma4:12b-it-qat)
| Métrica | v2.0 (llama-cpp-python) | v3.0 (Ollama) |
|---|---|---|
| Resposta curta completa | ~40 s | 0,9 s |
| Até a 1ª palavra | — | ~0,35 s |
| Geração | — | ~31 tokens/s |
| Modelo na GPU | não (CPU) | 100% |

## Consequências
- Dependência de um serviço externo ao Python (o Ollama precisa estar rodando). `scripts/diagnostico.py` verifica isso.
- Menos controle fino que o llama.cpp puro. Se um dia for preciso (ex.: offload específico de experts MoE), o `llama-server` é o plano B, e só o `cerebro.py` muda.
