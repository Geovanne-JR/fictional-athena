"""Carrega config/athena.toml num objeto tipado."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    modelo: str
    host: str
    num_ctx: int
    keep_alive: str
    pensar: bool
    amostragem: dict
    orcamento_historico: int
    pasta_dados: Path
    arquivo_persona: Path
    arquivo_perfil: Path
    nome_usuario: str
    temas_vigiados: list[str] = field(default_factory=list)
    ferramentas_ativas: bool = True

    @property
    def opcoes_ollama(self) -> dict:
        """Opções enviadas em TODA chamada. Precisam ser idênticas entre chamadas,
        senão o Ollama recarrega o modelo e perde o cache do prompt."""
        return {**self.amostragem, "num_ctx": self.num_ctx}


def carregar(caminho: Path | None = None) -> Config:
    caminho = caminho or RAIZ / "config" / "athena.toml"
    with open(caminho, "rb") as f:
        d = tomllib.load(f)

    perfil = RAIZ / d["persona"]["perfil_usuario"]
    if not perfil.exists():
        perfil = RAIZ / "config" / "perfil.exemplo.md"

    return Config(
        modelo=d["modelo"]["nome"],
        host=d["modelo"]["host"],
        num_ctx=int(d["modelo"]["num_ctx"]),
        keep_alive=str(d["modelo"]["keep_alive"]),
        pensar=bool(d["modelo"].get("pensar", False)),
        amostragem=dict(d.get("amostragem", {})),
        orcamento_historico=int(d["memoria"]["orcamento_historico_tokens"]),
        pasta_dados=RAIZ / d["memoria"]["pasta_dados"],
        arquivo_persona=RAIZ / d["persona"]["arquivo"],
        arquivo_perfil=perfil,
        nome_usuario=d["persona"].get("nome_usuario", "você"),
        temas_vigiados=[t.lower() for t in d["persona"].get("temas_vigiados", [])],
        ferramentas_ativas=bool(d.get("ferramentas", {}).get("ativas", True)),
    )
