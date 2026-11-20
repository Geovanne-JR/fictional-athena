"""Interface de terminal da Athena 3.0."""
from __future__ import annotations

import json
import sys

from rich.console import Console
from rich.panel import Panel

from .nucleo import Athena

AJUDA = """[bold]Comandos[/]
  /estado    mostra o estado interno dela (debug)
  /pensar    liga/desliga o raciocínio estendido (mais lento, mais inteligente)
  /metricas  liga/desliga o tempo de resposta e tokens/s
  /limpar    esquece a conversa atual (o estado emocional continua)
  /sair      encerra"""


def rodar(athena: Athena) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # acentos no PowerShell/CMD
    console = Console()
    nome = athena.cfg.nome_usuario
    mostrar_metricas = True

    console.print(Panel.fit(
        f"[bold magenta]ATHENA 3.0[/] · Projeto Olimpo\n[dim]cérebro: {athena.cerebro.modelo}[/]",
        border_style="magenta",
    ))

    if not athena.cerebro.modelo_instalado():
        console.print(f"[red]Modelo '{athena.cerebro.modelo}' não encontrado.[/] "
                      f"Rode: [bold]ollama pull {athena.cerebro.modelo}[/]")
        return

    with console.status("acordando a Athena (carregando o modelo na GPU)..."):
        segundos = athena.aquecer()
    gpu = athena.cerebro.uso_de_gpu()
    if gpu is None:
        cor_gpu = "[yellow]GPU: ?[/]"
    elif gpu >= 0.99:
        cor_gpu = "[green]100% na GPU[/]"
    else:
        cor_gpu = f"[red]{gpu:.0%} na GPU — parte está na CPU (vai ficar lento). Rode scripts/diagnostico.py[/]"
    console.print(f"[dim]pronta em {segundos:.1f}s ·[/] {cor_gpu}  [dim]· /ajuda pra comandos[/]\n")

    while True:
        try:
            texto = console.input(f"[bold cyan]{nome} ›[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texto:
            continue

        cmd = texto.lower()
        if cmd in ("/sair", "sair"):
            break
        if cmd == "/ajuda":
            console.print(AJUDA)
            continue
        if cmd == "/estado":
            console.print_json(json.dumps(athena.motor.resumo()))
            continue
        if cmd == "/pensar":
            athena.pensar = not athena.pensar
            console.print(f"[dim]raciocínio estendido: {'ligado' if athena.pensar else 'desligado'}[/]")
            continue
        if cmd == "/metricas":
            mostrar_metricas = not mostrar_metricas
            continue
        if cmd == "/limpar":
            athena.memoria.limpar()
            console.print("[dim]conversa esquecida.[/]")
            continue

        console.print("[bold magenta]Athena ›[/] ", end="")
        pensando = False
        try:
            for ev in athena.responder(texto):
                if ev.tipo == "pensamento":
                    if not pensando:
                        console.print("[dim italic](pensando...)[/] ", end="")
                        pensando = True
                elif ev.tipo == "texto":
                    sys.stdout.write(ev.dado)
                    sys.stdout.flush()
                elif ev.tipo == "ferramenta":
                    console.print(f"[dim]⚙ {ev.dado}...[/] ", end="")
                elif ev.tipo == "aviso":
                    console.print(f"\n[yellow]{ev.dado}[/]")
                elif ev.tipo == "metricas" and mostrar_metricas:
                    m = ev.dado
                    console.print(
                        f"\n[dim]⏱ 1ª palavra {m['primeira_palavra_s']}s · total {m['total_s']}s · "
                        f"{m['tokens_por_s']} tok/s · prompt {m['tokens_prompt']} tok em {m['prompt_s']}s[/]",
                        end="",
                    )
        except KeyboardInterrupt:
            console.print("\n[dim](interrompido)[/]", end="")
        except Exception as exc:
            console.print(f"\n[red]erro: {type(exc).__name__}: {exc}[/]", end="")
        console.print("\n")

    athena.motor.salvar()
    console.print("[dim]Athena desligando. Até mais.[/]")
