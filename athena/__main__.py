"""Ponto de entrada: `python -m athena` ou só `athena` com o venv ativo."""
from __future__ import annotations

import argparse
import sys

from .config import RAIZ, carregar
from .instancia import AthenaJaRodando, TravaDeInstancia
from .nucleo import Athena


def main() -> None:
    p = argparse.ArgumentParser(prog="athena", description="Athena 3.0 — Projeto Olimpo")
    p.add_argument("--modelo", help="sobrescreve o modelo da config (ex.: qwen3.5:9b)")
    p.add_argument("--sem-ferramentas", action="store_true", help="desliga o tool calling")
    p.add_argument("--servidor", action="store_true", help="abre a Athena pro navegador/celular (Etapa 2.5a)")
    p.add_argument("--gerar-token", action="store_true", help="cria a senha do servidor (ATHENA_TOKEN) no .env")
    args = p.parse_args()

    if args.gerar_token:
        from .servidor import gerar_token
        print("ATHENA_TOKEN criado no .env." if gerar_token(RAIZ / ".env")
              else "O .env já tem um ATHENA_TOKEN; nada mudou.")
        return

    cfg = carregar()
    if args.modelo:
        cfg.modelo = args.modelo
    if args.sem_ferramentas:
        cfg.ferramentas_ativas = False

    try:
        with TravaDeInstancia(cfg.pasta_dados):
            athena = Athena(cfg)  # carrega o estado emocional: só depois da trava
            if args.servidor:
                from .servidor import rodar_servidor
                rodar_servidor(athena)
            else:
                from .terminal import rodar
                rodar(athena)
    except AthenaJaRodando as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
