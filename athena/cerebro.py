"""
Cérebro: cliente do Ollama.

Por que Ollama e não llama-cpp-python (v2.0)?
- O Ollama já vem com o runtime CUDA embutido: nada de compilar wheel,
  nada de casar versão de CUDA Toolkit, nada de os.add_dll_directory.
  (A v2.0 apontava pras DLLs do CUDA 13.2, mas o PC tem o 12.4 — quase
  certamente a inferência caía na CPU. Daí os ~40s por resposta.)
- Servidor separado: o modelo fica quente na VRAM entre execuções do script.
- Trocar de modelo = mudar uma string na config.
- Tool calling e "thinking" nativos.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

from ollama import Client, ResponseError

from .config import Config


@dataclass
class Evento:
    tipo: str  # "texto" | "pensamento" | "ferramentas" | "ferramenta" | "metricas" | "aviso"
    dado: Any = None


@dataclass
class ChamadaFerramenta:
    nome: str
    argumentos: dict = field(default_factory=dict)


class Cerebro:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.modelo = cfg.modelo
        self.cliente = Client(host=cfg.host)
        self._aceita_think = True
        self._aceita_tools = True

    def conversar(self, mensagens: list[dict], ferramentas: list[dict] | None = None,
                  pensar: bool = False) -> Iterator[Evento]:
        kwargs: dict[str, Any] = dict(
            model=self.modelo,
            messages=mensagens,
            stream=True,
            options=self.cfg.opcoes_ollama,
            keep_alive=self.cfg.keep_alive,
        )
        if ferramentas and self._aceita_tools:
            kwargs["tools"] = ferramentas
        if self._aceita_think:
            kwargs["think"] = pensar

        inicio = time.perf_counter()
        primeiro_token: float | None = None
        chamadas: list[ChamadaFerramenta] = []
        try:
            for parte in self.cliente.chat(**kwargs):
                msg = parte.message
                if getattr(msg, "thinking", None):
                    yield Evento("pensamento", msg.thinking)
                if msg.content:
                    if primeiro_token is None:
                        primeiro_token = time.perf_counter() - inicio
                    yield Evento("texto", msg.content)
                for tc in msg.tool_calls or []:
                    chamadas.append(ChamadaFerramenta(tc.function.name, dict(tc.function.arguments or {})))
                if parte.done:
                    yield Evento("metricas", _metricas(parte, primeiro_token, time.perf_counter() - inicio))
        except ResponseError as e:
            erro = str(e).lower()
            if "think" in erro and self._aceita_think:
                self._aceita_think = False
                yield from self.conversar(mensagens, ferramentas, pensar)
                return
            if "tool" in erro and self._aceita_tools and ferramentas:
                self._aceita_tools = False
                yield Evento("aviso", f"o modelo {self.modelo} não aceita ferramentas; seguindo sem elas")
                yield from self.conversar(mensagens, None, pensar)
                return
            raise
        if chamadas:
            yield Evento("ferramentas", chamadas)

    def aquecer(self, system: str) -> float:
        """Carrega o modelo na VRAM e já processa o system prompt (fica no cache KV).
        Retorna os segundos gastos."""
        t = time.perf_counter()
        self.cliente.chat(
            model=self.modelo,
            messages=[{"role": "system", "content": system}],
            options={**self.cfg.opcoes_ollama, "num_predict": 1},
            keep_alive=self.cfg.keep_alive,
        )
        return time.perf_counter() - t

    def gerar_consulta(self, pergunta: str, hoje: str, conversa: list[str] | None = None,
                       ancora: str | None = None, contexto_local: str = "") -> str:
        """Reescreve a pergunta como consulta de busca curta. A pergunta crua dá
        consulta ruim ("o que rolou... UnB" achava a universidade do Canadá).

        Privacidade (decisão 008): a consulta sai do PC, então o perfil NÃO entra.
        Só a pergunta, a conversa recente, a consulta anterior (âncora: texto escrito
        por nós, nunca trecho de página) e, quando a pergunta depende de lugar, a
        cidade. O system é estático; o que muda vai na mensagem.
        Em caso de erro devolve a pergunta (com a âncora, se for um seguimento)."""
        partes = [f"Hoje é {hoje}."]
        if contexto_local:
            partes.append(f"Lugar de quem pergunta: {contexto_local}.")
        if conversa:
            # Sem isso, "qual a data do próximo jogo?" depois de falar do Barcelona
            # virou busca do Flamengo (time do perfil), no teste pelo celular.
            partes.append("Conversa até agora: " + " | ".join(conversa))
        if ancora:
            partes.append(f"Consulta anterior sobre este assunto: {ancora}")
        partes.append("Pergunta atual: " + pergunta)
        mensagem = "\n".join(partes)
        reserva = f"{ancora} {pergunta}" if ancora else pergunta  # "Quando?" puro não serve pro buscador
        try:
            r = self.cliente.chat(
                model=self.modelo,
                messages=[{"role": "system", "content": SYSTEM_CONSULTA}, {"role": "user", "content": mensagem}],
                options={**self.cfg.opcoes_ollama, "temperature": 0.2, "num_predict": 40},
                keep_alive=self.cfg.keep_alive,
                **({"think": False} if self._aceita_think else {}),
            )
            consulta = extrair_consulta(r.message.content or "")
        except Exception:
            return reserva
        if not 2 <= len(consulta) <= 200:
            return reserva
        # O modelo punha anos do treinamento ("eleições EUA 2024" em 2026, reteste da decisão
        # 008) mesmo com a instrução. Ano que ninguém citou e não é o atual sai da consulta.
        # Só autoriza ano dito por ELE (ou o de hoje), não um ano que a própria Athena falou;
        # e pega ano colado em pontuação ou data ("2024,", "(2024)", "03/11/2024") (Codex).
        falas_dele = [c for c in (conversa or []) if c.startswith("ele:")]
        citados = set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", " ".join([hoje, pergunta, ancora or "", *falas_dele])))
        consulta = " ".join(p for p in consulta.split()
                            if set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", p)) <= citados)
        return consulta or reserva

    def descarregar(self) -> bool:
        """Tira o modelo da VRAM na hora (keep_alive=0). Retorna False se o Ollama não respondeu."""
        try:
            self.cliente.generate(model=self.modelo, prompt="", keep_alive=0)
            return True
        except Exception:
            return False

    def uso_de_gpu(self) -> float | None:
        """Fração do modelo carregado que está na VRAM (1.0 = tudo na GPU)."""
        nomes = {self.modelo, f"{self.modelo}:latest"}  # "--modelo qwen3.5" aparece como "qwen3.5:latest"
        for m in self.cliente.ps().models:
            if m.model in nomes or m.name in nomes:
                return (m.size_vram or 0) / m.size if m.size else None
        return None

    def modelo_instalado(self) -> bool:
        nomes = {m.model for m in self.cliente.list().models}
        return self.modelo in nomes or f"{self.modelo}:latest" in nomes


SYSTEM_CONSULTA = (
    "Você transforma a pergunta atual numa consulta curta para um buscador da web, em português do Brasil. "
    "Quem pergunta mora no Brasil: em assunto que depende de país (eleição, governo, feriado, preço), "
    "o assunto é o do Brasil, a menos que ele cite outro país. "
    "Se a pergunta depende da conversa ('Quando?', 'o próximo jogo', 'e ele?'), use o assunto da conversa e a "
    "consulta anterior. Use 'resultado' ou 'placar' só para jogos, 'notícias' só para acontecimentos, 'data' "
    "quando ele pergunta quando algo foi ou será, e para software o nome em inglês com 'latest release'. "
    "Não use anos do seu treinamento: se precisar de um ano, use o de hoje ou um que ele tenha dito. "
    "Use o lugar de quem pergunta só se a pergunta depender de lugar (tempo, trânsito, 'perto'). "
    "Nunca coloque na consulta o nome, apelido ou dados pessoais de quem pergunta. "
    "Responda SÓ a consulta, sem aspas, sem explicação."
)


def extrair_consulta(resposta: str) -> str:
    """Primeira linha útil da resposta do modelo. Pula cerca de código, tags
    (<think>), preâmbulo ("Aqui está a consulta:") e tira aspas."""
    resposta = re.sub(r"<think>.*?</think>", "", resposta, flags=re.DOTALL)
    for linha in resposta.splitlines():
        linha = linha.strip().strip("\"'`*").strip()
        if not linha or linha.startswith(("```", "<")) or linha.endswith(":"):
            continue
        return re.sub(r"^(consulta|busca|query)\s*:\s*", "", linha, flags=re.IGNORECASE).strip("\"'` ")
    return ""


def _metricas(parte, primeiro_token: float | None, total: float) -> dict:
    ns = 1e9
    eval_n = parte.eval_count or 0
    eval_s = (parte.eval_duration or 0) / ns
    return {
        "tokens_gerados": eval_n,
        "tokens_por_s": round(eval_n / eval_s, 1) if eval_s else None,
        "tokens_prompt": parte.prompt_eval_count or 0,
        "prompt_s": round((parte.prompt_eval_duration or 0) / ns, 2),
        "carga_s": round((parte.load_duration or 0) / ns, 2),
        "primeira_palavra_s": round(primeiro_token, 2) if primeiro_token else None,
        "total_s": round(total, 2),
    }
