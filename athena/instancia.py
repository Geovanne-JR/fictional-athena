"""Garante uma Athena só por vez (terminal OU servidor).

Cada processo carrega o estado emocional no início e salva por cima no fim.
Com dois processos ao mesmo tempo, um apagaria o que o outro viveu. A trava é
um arquivo com lock do sistema operacional: some sozinha se o processo morrer.
"""
from __future__ import annotations

import os
from pathlib import Path


class AthenaJaRodando(RuntimeError):
    pass


class TravaDeInstancia:
    def __init__(self, pasta: Path):
        self.caminho = pasta / "athena.lock"
        self._arq = None

    def __enter__(self) -> "TravaDeInstancia":
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        arq = open(self.caminho, "a+")
        try:
            _travar(arq)
        except OSError:
            arq.close()
            raise AthenaJaRodando(
                "Já tem uma Athena rodando (terminal ou servidor). Feche a outra antes."
            ) from None
        self._arq = arq
        return self

    def __exit__(self, *exc) -> None:
        if self._arq:
            try:
                _destravar(self._arq)
            finally:
                self._arq.close()
                self._arq = None


if os.name == "nt":
    import msvcrt

    def _travar(arq) -> None:
        arq.seek(0)
        msvcrt.locking(arq.fileno(), msvcrt.LK_NBLCK, 1)

    def _destravar(arq) -> None:
        arq.seek(0)
        msvcrt.locking(arq.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _travar(arq) -> None:
        fcntl.flock(arq.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _destravar(arq) -> None:
        fcntl.flock(arq.fileno(), fcntl.LOCK_UN)
