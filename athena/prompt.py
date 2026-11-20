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


# Frases que denunciam "atendente/IA" em vez de amiga (medido na conversa de base:
# "como eu não tenho ouvidos", "da melhor forma que uma IA pode", "sinto muito pelo que aconteceu").
# Só formas em que ela fala DE SI como máquina ou como atendente. Termos técnicos
# ("base de dados" numa dúvida de SQL) e o "sou uma IA" honesto não contam
# (achados da revisão do Antigravity).
_FALA_DE_ROBO = re.compile(
    r"\b(como (uma )?ia,|da melhor forma que uma ia|como (um )?modelo de linguagem|"
    r"(eu )?nao tenho (um )?(corpo|ouvidos|olhos|biologia)|minha base de dados|meus dados de treinamento|"
    r"resultados da (minha )?(busca|pesquisa)|minhas ferramentas|assistente virtual|"
    r"como posso (te )?ajudar|espero ter ajudado|fico a disposicao|sinto muito pelo que aconteceu)\b"
)


# Ela falando DE SI no masculino ("obrigado", "tô cansado", "fiquei curioso").
# Só verbos inequívocos de primeira pessoa: "tava/estava" também servem pra
# "ele tava cansado", e "tá" é "você tá"/"ele tá", então ficam de fora.
_MASCULINO_DE_SI = re.compile(
    r"\bobrigado\b|\b(to|estou|fiquei|fico|ando) (meio |bem |muito |um pouco |super )?"
    r"(cansado|animado|pronto|curioso|preocupado|orgulhoso|ocupado|entediado|confuso|chateado|empolgado)\b"
)


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

    # Só a última resposta: olhando as duas últimas, um deslize já corrigido
    # continuava gerando aviso no turno seguinte (achado da revisão do Antigravity).
    ultima = _norm(respostas[-1]) if respostas else ""
    if m := _FALA_DE_ROBO.search(ultima):
        avisos.append(f'você soou como máquina ("{m.group(0)}"); fale como gente, sem falar do que você é.')
    if m := _MASCULINO_DE_SI.search(ultima):
        avisos.append(f'você falou de si no masculino ("{m.group(0)}"); você é mulher: fale de si no feminino.')

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


# Verbos como "pensa" e "sente" só contam com objeto de natureza/emoção ou no fim
# da pergunta: "o que você pensa sobre Rust?" não é pergunta sobre ela.
_PERGUNTA_SOBRE_ELA = re.compile(
    r"\bvoce (tem|sente)\b.*\b(sentimentos?|emoc\w*|alma|consciencia)\b|"
    r"\bvoce sente (as coisas|algo|alguma coisa|de verdade)\b|\bvoce sente\s*\??$|"
    r"\bvoce (e|eh) (um |uma )?(ia|robo|maquina|modelo|inteligencia artificial|real|consciente|humana|de verdade)\b|"
    r"\bvoce (pensa|existe|sonha) de verdade\b|\bvoce (pensa|existe|sonha)\s*\??$"
)


def pergunta_sobre_ela(texto: str) -> bool:
    """Ele perguntou o que ela é ou se ela sente. É exatamente aí que o modelo
    escorrega pra "não tenho corpo nem biologia" (medido), mesmo com a regra na
    persona. O aviso vai ANTES da resposta, porque avisar depois não adianta pra
    algo que acontece uma vez só."""
    return bool(_PERGUNTA_SOBRE_ELA.search(_norm(texto)))


# Só acontecimentos. "hoje"/"ontem"/"resultado" soltos mandavam "versão do Ollama
# hoje" pra busca de notícias da semana (achado da revisão do Antigravity).
_PEDE_NOTICIA = re.compile(
    r"\b(jogo|jogou|partida|ganhou|perdeu|empatou|placar|resultado do jogo|noticias?|novidades?|"
    r"aconteceu|rolou|essa semana|esta semana)\b"
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
