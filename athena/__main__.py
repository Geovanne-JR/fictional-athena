"""Ponto de entrada: `python -m athena` ou só `athena` com o venv ativo."""
from __future__ import annotations

import argparse

from .config import carregar
from .nucleo import Athena
from .terminal import rodar


def main() -> None:
    p = argparse.ArgumentParser(prog="athena", description="Athena 3.0 — Projeto Olimpo")
    p.add_argument("--modelo", help="sobrescreve o modelo da config (ex.: qwen3.5:9b)")
    p.add_argument("--sem-ferramentas", action="store_true", help="desliga o tool calling")
    args = p.parse_args()

    cfg = carregar()
    if args.modelo:
        cfg.modelo = args.modelo
    if args.sem_ferramentas:
        cfg.ferramentas_ativas = False
    rodar(Athena(cfg))


if __name__ == "__main__":
    main()
