"""Carrega config/athena.toml num objeto tipado."""
from __future__ import annotations

import os
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
    porta_servidor: int = 8765
    sessao_minutos: int = 30

    @property
    def opcoes_ollama(self) -> dict:
        """Opções enviadas em TODA chamada. Precisam ser idênticas entre chamadas,
        senão o Ollama recarrega o modelo e perde o cache do prompt."""
        return {**self.amostragem, "num_ctx": self.num_ctx}


# Só o que a Athena usa. O .env também guarda chaves de outras ferramentas
# (ex.: BOB_API_KEY, do auditor), e a Athena não precisa recebê-las.
CHAVES_DA_ATHENA = frozenset({"TAVILY_API_KEY", "ATHENA_TOKEN"})


def carregar_env(caminho: Path, permitidas: frozenset[str] = CHAVES_DA_ATHENA) -> None:
    """Lê KEY=VALOR do .env pro ambiente, sem sobrescrever o que já existe e só
    para as chaves permitidas. O .env guarda segredos e fica fora do git."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        if chave.strip() in permitidas:
            os.environ.setdefault(chave.strip(), _valor_env(valor))


def _valor_env(valor: str) -> str:
    """'"tvly-x" # comentário' → 'tvly-x'. Entre aspas vale o que está dentro;
    sem aspas, ' #' começa um comentário."""
    valor = valor.strip()
    if valor[:1] in ("'", '"'):
        fim = valor.find(valor[0], 1)
        return valor[1:fim] if fim != -1 else valor[1:]
    return valor.split(" #", 1)[0].strip()


def carregar(caminho: Path | None = None) -> Config:
    carregar_env(RAIZ / ".env")
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
        porta_servidor=int(d.get("servidor", {}).get("porta", 8765)),
        sessao_minutos=int(d.get("servidor", {}).get("sessao_minutos", 30)),
    )
