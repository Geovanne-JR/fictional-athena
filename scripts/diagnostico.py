"""
Diagnóstico do ambiente da Athena. Rode sempre que algo parecer lento:

    .venv\\Scripts\\python scripts\\diagnostico.py [--modelo nome]

Responde a pergunta que a v2.0 nunca respondeu: o modelo está MESMO na GPU?
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

from rich.console import Console
from rich.table import Table

from athena.cerebro import Cerebro
from athena.config import carregar
from athena.prompt import montar_system

PERGUNTAS = [
    "Explica em 3 frases o que é uma árvore AVL.",
    "Me dá uma dica rápida pra estudar pra prova de cálculo.",
    "Qual a diferença entre TCP e UDP? Seja breve.",
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", action="append", help="pode repetir pra comparar modelos")
    args = ap.parse_args()

    con = Console()
    cfg = carregar()
    ok = True

    con.rule("[bold]Ambiente")
    con.print(f"Python {sys.version.split()[0]}")
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.used,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        con.print(f"GPU: {gpu}")
    except (OSError, subprocess.SubprocessError):
        con.print("[red]nvidia-smi não encontrado — driver NVIDIA ok?[/]")
        ok = False

    cerebro = Cerebro(cfg)
    try:
        versao = cerebro.cliente._client.get("/api/version").json()["version"]
        con.print(f"Ollama {versao} respondendo em {cfg.host}")
    except Exception as exc:
        con.print(f"[red]Ollama não responde em {cfg.host}: {exc}[/]\nAbra o app Ollama ou rode `ollama serve`.")
        return 1

    system = montar_system(cfg)
    tabela = Table(title="Desempenho (com o system prompt real da Athena)")
    for col in ("modelo", "% na GPU", "carga", "prompt (1ª vez)", "1ª palavra (cache)", "tok/s"):
        tabela.add_column(col)

    for modelo in args.modelo or [cfg.modelo]:
        cfg.modelo = modelo
        cerebro = Cerebro(cfg)
        if not cerebro.modelo_instalado():
            con.print(f"[red]{modelo} não está instalado.[/] ollama pull {modelo}")
            ok = False
            continue

        con.rule(f"[bold]{modelo}")
        carga = cerebro.aquecer(system)
        fracao = cerebro.uso_de_gpu() or 0
        cor = "green" if fracao >= 0.99 else "red"
        if fracao < 0.99:
            ok = False

        metricas = []
        for p in PERGUNTAS:
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": p}]
            texto = ""
            for ev in cerebro.conversar(msgs):
                if ev.tipo == "texto":
                    texto += ev.dado
                elif ev.tipo == "metricas":
                    metricas.append(ev.dado)
            con.print(f"[cyan]› {p}[/]\n{texto.strip()}\n")
            time.sleep(0.2)

        tps = sum(m["tokens_por_s"] or 0 for m in metricas) / len(metricas)
        ttft = sum(m["primeira_palavra_s"] or 0 for m in metricas) / len(metricas)
        tabela.add_row(modelo, f"[{cor}]{fracao:.0%}[/]", f"{carga:.1f}s", f"{metricas[0]['prompt_s']}s",
                       f"{ttft:.2f}s", f"{tps:.1f}")

    con.print(tabela)
    if ok:
        con.print("[green bold]Tudo certo: modelo 100% na GPU.[/]")
    else:
        con.print("[red bold]Atenção:[/] parte do modelo está na CPU. Feche apps que usam VRAM "
                  "(wallpaper animado, jogos, navegador com aceleração), reduza num_ctx em "
                  "config/athena.toml ou use um modelo menor.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
