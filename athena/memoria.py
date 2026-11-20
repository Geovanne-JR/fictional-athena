"""
Memória de curto prazo (janela de conversa) + diário em disco.

- A janela é por ORÇAMENTO DE TOKENS, não por número fixo de trocas.
- Guarda turnos inteiros (user + chamadas de ferramenta + resposta), então
  nunca sobra uma mensagem de ferramenta órfã quando o histórico é cortado.
- Corta em blocos (até 60% do orçamento) em vez de um turno por vez:
  assim o prefixo do prompt muda raramente e o Ollama reaproveita o cache KV.
- O diário (data/conversas/AAAA-MM-DD.jsonl) é a matéria-prima da Etapa 3
  (memória de longo prazo).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def estimar_tokens(texto: str) -> int:
    # ~3 caracteres por token em português é uma estimativa conservadora
    return len(texto) // 3 + 4


def _tokens_msg(m: dict) -> int:
    extra = json.dumps(m.get("tool_calls", []), ensure_ascii=False) if m.get("tool_calls") else ""
    return estimar_tokens((m.get("content") or "") + extra)


LIMITE_FERRAMENTA_NO_HISTORICO = 600  # caracteres


def compactar_ferramenta(conteudo: str) -> str:
    """Resultado de ferramenta enxuto pro histórico. Uma busca com páginas lidas
    tem ~2 mil tokens; guardar inteiro faria três buscas comerem o orçamento.
    A resposta da Athena já carrega o que importava; aqui fica só a referência."""
    if len(conteudo) <= LIMITE_FERRAMENTA_NO_HISTORICO:
        return conteudo
    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError:
        dados = None
    if isinstance(dados, dict) and isinstance(dados.get("resultados"), list):
        refs = [{k: r[k] for k in ("titulo", "url", "data") if r.get(k)} for r in dados["resultados"]]
        return json.dumps({"consulta": dados.get("consulta"), "fonte_busca": dados.get("fonte_busca"), "resultados": refs,
                           "obs": "conteúdo das páginas omitido no histórico"}, ensure_ascii=False)
    if isinstance(dados, dict) and "texto" in dados:
        return json.dumps({"url": dados.get("url"), "obs": "texto da página omitido no histórico"},
                          ensure_ascii=False)
    return conteudo[:LIMITE_FERRAMENTA_NO_HISTORICO] + "…(cortado no histórico)"


class MemoriaCurta:
    def __init__(self, orcamento_tokens: int):
        self.orcamento = orcamento_tokens
        self.turnos: list[list[dict]] = []

    def adicionar_turno(self, mensagens: list[dict]) -> None:
        compacto = [
            {**m, "content": compactar_ferramenta(m.get("content") or "")} if m["role"] == "tool" else m
            for m in mensagens
        ]
        self.turnos.append(compacto)
        self._aparar()

    def _total(self) -> int:
        return sum(_tokens_msg(m) for t in self.turnos for m in t)

    def _aparar(self) -> None:
        if self._total() <= self.orcamento:
            return
        alvo = int(self.orcamento * 0.6)
        while len(self.turnos) > 1 and self._total() > alvo:
            self.turnos.pop(0)

    def mensagens(self) -> list[dict]:
        return [m for t in self.turnos for m in t]

    def ultimas_respostas(self, n: int) -> list[str]:
        out = []
        for t in self.turnos[-n:]:
            finais = [m["content"] for m in t if m["role"] == "assistant" and m.get("content")]
            if finais:
                out.append(finais[-1])
        return out

    def ultimas_perguntas(self, n: int) -> list[str]:
        return [t[0]["content"] for t in self.turnos[-n:] if t and t[0]["role"] == "user"]

    def limpar(self) -> None:
        self.turnos.clear()


class Diario:
    def __init__(self, pasta: Path):
        self.pasta = pasta

    def registrar(self, **dados) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        agora = datetime.now()
        arquivo = self.pasta / f"{agora:%Y-%m-%d}.jsonl"
        linha = {"ts": agora.isoformat(timespec="seconds"), **dados}
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
