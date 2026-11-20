"""
Motor emocional da Athena.

Diferente da v2.0 (um texto fixo por faixa de horário), aqui o estado é
contínuo e reage a eventos:

- energia      0..1   curva circadiana (calculada, não armazenada)
- humor       -1..1   sobe com elogio/agradecimento, cai com grosseria
- paciencia    0..1   cai com grosseria e mensagem repetida
- curiosidade  0..1   sobe com sinais de interesse no assunto
- vinculo      0..1   cresce devagar a cada conversa e NÃO decai (relação)

Tudo (menos vínculo) volta sozinho pra linha de base com o tempo
(decaimento exponencial), então irritação passa e animação esfria.

Ela também "percebe" o clima do Gegê (estressado, triste, animado...) e isso
muda o quanto de humor é apropriado — o vício da v2.0 era fazer piada sempre.

O estado é renderizado como frases curtas e sutis pro bloco [contexto],
nunca como um roteiro de teatro.
"""
from __future__ import annotations

import json
import math
import re
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

BASE = {"humor": 0.25, "paciencia": 0.75, "curiosidade": 0.5}
TAU_MIN = {"humor": 60.0, "paciencia": 30.0, "curiosidade": 20.0}  # meia-vida aprox.
DURACAO_CLIMA_S = 20 * 60  # percepção do clima dele vale por 20 min

_P = lambda s: re.compile(s, re.IGNORECASE)  # noqa: E731

SINAIS = {
    "hostil": _P(r"\b(burra|idiota|inutil|lixo|imbecil|retardada|cala a boca|vai se f|merda de ia|ia burra)\b"),
    "elogio": _P(r"\b(mandou bem|perfeit[oa]|genial|incrivel|brabo|braba|sensacional|te amo|melhor ia|boa athena|muito bom)\b"),
    "agradecimento": _P(r"\b(valeu|obrigad[oa]|vlw|brigad[oa]|tmj)\b"),
    "tristeza": _P(r"\b(triste|chatead[oa]|deprimid[oa]|sozinh[oa]|desanimad[oa]|t[oô] mal|me sentindo mal|vontade de chorar)\b"),
    "estresse": _P(r"\b(prova|deadline|prazo|desesper\w*|socorro|ferrou|cansad[oa]|estressad[oa]|ansios[oa]|nao aguento|urgente|reprovar)\b"),
    "animacao": _P(r"(!{2,}|\bk{3,}\b|\b(ha){2,}\b|\bbora\b|\bvamo\b|\buhu+\b|\bpartiu\b|\bvenceu\b|\bganhamos\b)"),
    "curioso": _P(r"\b(como funciona|por que|explica|ideia|o que voce acha|sera que)\b"),
}


_DESPEDIDA = re.compile(
    r"\b(tchau|xau|ate (mais|amanha|logo|depois|a proxima)|falou|flw|fui|vou dormir|vou nessa|"
    r"vou sair|vou indo|pode descansar|desliga|boa noite)\b"
)


def eh_despedida(texto: str, ja_conversou: bool) -> bool:
    """Mensagem curta de tchau. 'boa noite' só conta se já houve conversa
    (no começo da sessão é cumprimento). Pergunta nunca é despedida."""
    t = _normalizar(texto)
    if "?" in t or len(t.split()) > 8:
        return False
    achados = {m.group(0) for m in _DESPEDIDA.finditer(t)}
    if not achados:
        return False
    if achados == {"boa noite"}:
        return ja_conversou
    return True


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def detectar_sinais(texto: str) -> set[str]:
    t = _normalizar(texto)
    # "tô mal" perde o acento na normalização; testa o original também
    return {nome for nome, rx in SINAIS.items() if rx.search(t) or rx.search(texto.lower())}


def energia_circadiana(hora: float) -> float:
    """0..1. Pico de manhã (~10h30) e à noite (~21h), vale de madrugada (~4h)."""

    def pico(centro: float, largura: float) -> float:
        d = abs(hora - centro)
        d = min(d, 24 - d)
        return math.exp(-(d * d) / (2 * largura * largura))

    return round(min(1.0, 0.15 + 0.65 * pico(10.5, 3.5) + 0.6 * pico(21.0, 3.0)), 3)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class Estado:
    humor: float = BASE["humor"]
    paciencia: float = BASE["paciencia"]
    curiosidade: float = BASE["curiosidade"]
    vinculo: float = 0.3
    clima_usuario: str = "neutro"
    clima_ate: float = 0.0
    interacoes: int = 0
    atualizado_em: float = field(default_factory=time.time)


class MotorEmocional:
    def __init__(self, caminho: Path | None = None):
        self.caminho = caminho
        self.estado = self._carregar()
        self._ultima_msg = ""
        self._ultima_msg_triste = False

    # ── persistência ────────────────────────────────────────────
    def _carregar(self) -> Estado:
        if self.caminho and self.caminho.exists():
            try:
                dados = json.loads(self.caminho.read_text(encoding="utf-8"))
                campos = Estado.__dataclass_fields__
                return Estado(**{k: v for k, v in dados.items() if k in campos})
            except (json.JSONDecodeError, TypeError):
                pass
        return Estado()

    def salvar(self) -> None:
        if not self.caminho:
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(json.dumps(asdict(self.estado), indent=2), encoding="utf-8")

    # ── dinâmica ────────────────────────────────────────────────
    def decair(self, agora_ts: float) -> None:
        e = self.estado
        dt_min = max(0.0, (agora_ts - e.atualizado_em) / 60.0)
        for nome, base in BASE.items():
            atual = getattr(e, nome)
            fator = math.exp(-dt_min / TAU_MIN[nome])
            setattr(e, nome, base + (atual - base) * fator)
        if agora_ts > e.clima_ate:
            e.clima_usuario = "neutro"
        e.atualizado_em = agora_ts

    def perceber(self, texto: str, agora: datetime | None = None) -> set[str]:
        """Atualiza o estado a partir de uma mensagem do Gegê. Retorna os sinais detectados."""
        agora = agora or datetime.now()
        ts = agora.timestamp()
        self.decair(ts)
        e = self.estado
        s = detectar_sinais(texto)
        self._ultima_msg_triste = "tristeza" in s

        if "elogio" in s:
            e.humor += 0.15
            e.vinculo += 0.01
        if "agradecimento" in s:
            e.humor += 0.07
            e.vinculo += 0.005
        if "hostil" in s:
            e.humor -= 0.3
            e.paciencia -= 0.25
        if "curioso" in s:
            e.curiosidade += 0.12
        if "animacao" in s:
            e.humor += 0.05

        norm = _normalizar(texto)
        if norm and norm == self._ultima_msg:
            e.paciencia -= 0.12
            s.add("repetida")
        self._ultima_msg = norm

        # Prioridade do clima percebido: hostil > triste > estressado > animado
        for sinal, clima in (("hostil", "rispido_com_voce"), ("tristeza", "triste"),
                             ("estresse", "estressado"), ("animacao", "animado")):
            if sinal in s:
                e.clima_usuario = clima
                e.clima_ate = ts + DURACAO_CLIMA_S
                break

        e.vinculo += 0.002
        e.interacoes += 1
        e.humor = _clamp(e.humor, -1.0, 1.0)
        for nome in ("paciencia", "curiosidade", "vinculo"):
            setattr(e, nome, _clamp(getattr(e, nome), 0.0, 1.0))
        return s

    # ── leitura ─────────────────────────────────────────────────
    def energia(self, agora: datetime) -> float:
        return energia_circadiana(agora.hour + agora.minute / 60)

    def nivel_de_humor(self, agora: datetime) -> str:
        """'nenhum' | 'discreto' | 'liberado' — quanto de piada cabe agora."""
        e, energia = self.estado, self.energia(agora)
        if e.clima_usuario in ("triste", "estressado"):
            return "nenhum"
        if e.humor > 0.35 and energia > 0.5:
            return "liberado"
        return "discreto"

    def descrever(self, agora: datetime, nome_usuario: str = "o Gegê") -> str:
        e, energia = self.estado, self.energia(agora)
        partes = []

        if energia < 0.35:
            partes.append("com pouca energia (horário puxado), mais econômica nas palavras")
        elif energia < 0.6:
            partes.append("com energia normal")
        else:
            partes.append("com bastante energia")

        if e.humor > 0.55:
            partes.append("de ótimo humor")
        elif e.humor > 0.1:
            partes.append("de bom humor")
        elif e.humor > -0.25:
            partes.append("meio neutra")
        else:
            partes.append("chateada com o jeito que ele te tratou")

        if e.paciencia < 0.4:
            partes.append("com a paciência curta")
        if e.curiosidade > 0.7:
            partes.append("interessada na conversa")

        linhas = ["Você está " + ", ".join(partes) + "."]

        clima = {
            "estressado": f"{nome_usuario} parece estressado ou sob pressão: foco total em ajudar, objetiva.",
            "animado": f"{nome_usuario} está animado: pode acompanhar a energia dele.",
            "rispido_com_voce": f"{nome_usuario} foi ríspido com você: pode mostrar de leve que não curtiu, sem drama, e siga ajudando.",
        }.get(e.clima_usuario)
        if e.clima_usuario == "triste":
            if self._ultima_msg_triste:
                clima = (f"{nome_usuario} parece pra baixo. Acolha como amiga numa frase curta, tipo ‘ah, não…’ ou ‘que droga’. "
                         "Evite ‘sinto muito’ e ‘tô aqui com/pra você’. Sem oferta de ajuda nem convite a desabafar. "
                         "Se ele fez um pedido objetivo, responda ao pedido em seguida.")
            else:
                clima = (f"{nome_usuario} comentou há pouco que estava pra baixo. "
                         "Siga o assunto dele com leveza, sem reabrir o tema.")
        if clima:
            linhas.append(clima)

        linhas.append({
            "nenhum": "Humor: nenhum agora.",
            "discreto": "Humor: discreto; só se surgir sozinho.",
            "liberado": "Humor: liberado (uma tirada no máximo, se couber).",
        }[self.nivel_de_humor(agora)])

        if e.vinculo > 0.75:
            linhas.append("Vocês já têm bastante intimidade.")
        return " ".join(linhas)

    def resumo(self, agora: datetime | None = None) -> dict:
        agora = agora or datetime.now()
        d = asdict(self.estado)
        d["energia"] = self.energia(agora)
        d["nivel_de_humor"] = self.nivel_de_humor(agora)
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}
