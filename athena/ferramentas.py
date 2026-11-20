"""
Registro de ferramentas (tool calling).

Por enquanto só ferramentas de LEITURA. Ferramentas que mudam algo no PC
(abrir programa, mexer em volume, ventoinha...) entram na Etapa 5 com uma
camada de confirmação. Ver docs/ARQUITETURA.md.

Pra criar uma ferramenta nova:

    @ferramenta("nome", "quando usar", {"cidade": {"type": "string", "description": "..."}})
    def nome(cidade: str) -> dict: ...
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

import psutil


@dataclass
class Ferramenta:
    nome: str
    descricao: str
    parametros: dict
    obrigatorios: list[str]
    funcao: Callable[..., Any]


REGISTRO: dict[str, Ferramenta] = {}


def ferramenta(nome: str, descricao: str, parametros: dict | None = None, obrigatorios: list[str] | None = None):
    def registrar(fn: Callable[..., Any]) -> Callable[..., Any]:
        REGISTRO[nome] = Ferramenta(nome, descricao, parametros or {}, obrigatorios or [], fn)
        return fn
    return registrar


def esquemas() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": f.nome,
                "description": f.descricao,
                "parameters": {"type": "object", "properties": f.parametros, "required": f.obrigatorios},
            },
        }
        for f in REGISTRO.values()
    ]


def executar(nome: str, argumentos: dict | None) -> str:
    f = REGISTRO.get(nome)
    if not f:
        return json.dumps({"erro": f"ferramenta '{nome}' não existe"}, ensure_ascii=False)
    try:
        resultado = f.funcao(**(argumentos or {}))
    except Exception as exc:  # o modelo precisa ver o erro pra se corrigir
        resultado = {"erro": f"{type(exc).__name__}: {exc}"}
    return json.dumps(resultado, ensure_ascii=False, default=str)


# ─────────────────────────────────────────────────────────────
#  Ferramentas
# ─────────────────────────────────────────────────────────────
def _gpu() -> dict:
    campos = "name,temperature.gpu,utilization.gpu,memory.used,memory.total,fan.speed,power.draw"
    try:
        saida = subprocess.run(
            ["nvidia-smi", f"--query-gpu={campos}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return {"erro": "nvidia-smi indisponível"}
    nome, temp, uso, usada, total, fan, watts = [c.strip() for c in saida.split(",")]
    return {
        "nome": nome,
        "temperatura_c": temp,
        "uso_pct": uso,
        "vram_usada_mb": usada,
        "vram_total_mb": total,
        "ventoinha_pct": fan,
        "consumo_w": watts,
    }


@ferramenta(
    "status_do_pc",
    "Lê o estado atual do PC do Gegê: uso de CPU e RAM, temperatura, uso e VRAM da GPU, "
    "ventoinha da GPU e há quanto tempo o PC está ligado. Use quando ele perguntar do PC, "
    "desempenho, temperatura, memória ou se algo está pesado.",
)
def status_do_pc() -> dict:
    ram = psutil.virtual_memory()
    ligado_h = (time.time() - psutil.boot_time()) / 3600
    return {
        "cpu_uso_pct": psutil.cpu_percent(interval=0.3),
        "ram_usada_gb": round(ram.used / 2**30, 1),
        "ram_total_gb": round(ram.total / 2**30, 1),
        "gpu": _gpu(),
        "ligado_ha_horas": round(ligado_h, 1),
        "obs": "temperatura da CPU não é exposta pelo Windows sem ferramenta extra (Etapa 5)",
    }
