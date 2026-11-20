"""
Montagem do prompt.

Decisão importante de desempenho: o system prompt é 100% ESTÁTICO.
Tudo que muda a cada mensagem (hora, estado emocional, avisos) vai num bloco
[contexto] colado na mensagem atual do Gegê. Assim o prefixo
(system + histórico) é idêntico entre mensagens e o Ollama reaproveita o
cache KV — só processa os tokens novos. Na v2.0 a hora ficava no system
prompt, e isso invalidava o cache inteiro toda vez.

Também mora aqui o anti-repetição: o remédio direto pro vício da v2.0
de começar toda resposta igual e falar de nuvem/Flamengo sem ninguém pedir.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from .config import Config

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def montar_system(cfg: Config) -> str:
    persona = cfg.arquivo_persona.read_text(encoding="utf-8").strip()
    perfil = cfg.arquivo_perfil.read_text(encoding="utf-8").strip()
    return f"{persona}\n\n{perfil}"


def periodo_do_dia(hora: int) -> str:
    if hora < 6:
        return "madrugada"
    if hora < 12:
        return "manhã"
    if hora < 18:
        return "tarde"
    return "noite"


def _norm(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def _abertura(texto: str, n: int = 3) -> str:
    palavras = re.findall(r"\w+", _norm(texto))
    return " ".join(palavras[:n])


def analisar_repeticao(respostas: list[str], perguntas: list[str], temas: list[str]) -> list[str]:
    """Olha as últimas respostas dela e devolve avisos curtos pro [contexto]."""
    avisos: list[str] = []

    aberturas = [_abertura(r) for r in respostas[-3:] if r.strip()]
    if len(aberturas) >= 2:
        repetida = max(set(aberturas), key=aberturas.count)
        if aberturas.count(repetida) >= 2:
            avisos.append(f'suas últimas respostas começaram com "{repetida}..."; comece de outro jeito.')

    finais_com_pergunta = sum(1 for r in respostas[-3:] if r.rstrip().endswith("?"))
    if finais_com_pergunta >= 2:
        avisos.append("você tem terminado as respostas com pergunta; desta vez termine sem perguntar nada.")

    perguntas_norm = " ".join(_norm(p) for p in perguntas)
    respostas_norm = [_norm(r) for r in respostas[-4:]]
    for tema in temas:
        t = _norm(tema)
        vezes = sum(1 for r in respostas_norm if re.search(rf"\b{re.escape(t)}\b", r))
        if vezes >= 2 and not re.search(rf"\b{re.escape(t)}\b", perguntas_norm):
            avisos.append(f'você puxou "{tema}" {vezes}x sem ele pedir; deixe esse assunto de lado.')
    return avisos


# Só termos fortes. Palavras soltas como "hoje", "agora" ou "resultado" disparavam
# busca em "como você está hoje?" e "resultado de 2+2" (achado da revisão do Antigravity).
_PEDE_ATUALIDADE = re.compile(
    r"\b(ultim[oa]s? (jogo|partida|noticia|versao|lancamento|resultado|episodio|temporada)|"
    r"(jogo|noticias?|cotacao|previsao|placar) de (hoje|ontem)|"
    r"essa semana|esta semana|esse mes|este mes|noticias?|novidades?|lancamento|lancou|"
    r"versao mais recente|versao atual|precos?|quanto (ta|esta|custa)|cotacao|placar|"
    r"resultado do jogo|quem ganhou|ganhou|perdeu|empatou|classificacao|previsao do tempo|vai chover)\b"
)


def pede_atualidade(texto: str) -> bool:
    """Heurística barata: a pergunta parece depender de informação atual?
    O modelo sozinho decide mal quando buscar (inventou versão do Ollama e
    "pesquisou" notícias sem chamar a ferramenta). Falso positivo custa só
    uma busca a mais (~3s); falso negativo custa uma resposta inventada."""
    return bool(_PEDE_ATUALIDADE.search(_norm(texto)))


_PEDE_NOTICIA = re.compile(
    r"\b(jogo|jogou|ganhou|perdeu|empatou|placar|resultado|noticias?|novidades?|essa semana|esta semana|hoje|ontem)\b"
)


def tipo_de_busca(texto: str) -> str:
    """'noticias' para acontecimentos (jogos, notícias); 'geral' para o resto (versões, preços...)."""
    return "noticias" if _PEDE_NOTICIA.search(_norm(texto)) else "geral"


def bloco_contexto(agora: datetime, descricao_estado: str, avisos: list[str]) -> str:
    linhas = [
        "[contexto — privado, não mencione]",
        f"Agora: {DIAS[agora.weekday()]}, {agora:%d/%m/%Y}, {agora:%H:%M} ({periodo_do_dia(agora.hour)}).",
        descricao_estado,
    ]
    if avisos:
        linhas.append("Avisos: " + " ".join(avisos))
    linhas.append("[/contexto]")
    return "\n".join(linhas)
