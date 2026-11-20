"""Continuidade, buscas e privacidade (decisão 008). Offline: cérebro e buscador falsos.

Roteiro inspirado no teste real pelo celular: Barcelona → eleições → "Quando?" →
dólar → "tem certeza?" → "Fiquei doente no dia".
"""
import json

import pytest

from athena import ferramentas as fer
from athena import nucleo
from athena.cerebro import ChamadaFerramenta, Evento
from athena.config import carregar
from athena.prompt import pede_atualidade, pergunta_de_seguimento, tipo_de_busca

RESULTADO_OK = json.dumps({"consulta": "x", "fonte_busca": "tavily",
                           "resultados": [{"titulo": "t", "url": "https://a", "data": "2026-11-19"}]})
RESULTADO_FALHOU = json.dumps({"erro": "RuntimeError: busca sem resultado", "obs": fer.OBS_FALHA})


class CerebroFalso:
    modelo = "falso"

    def __init__(self, roteiros=None):
        self.roteiros = list(roteiros or [])
        self.enviadas = []        # mensagens de cada chamada a conversar()
        self.consultas = []       # argumentos de cada gerar_consulta()

    def conversar(self, mensagens, ferramentas=None, pensar=False):
        self.enviadas.append(mensagens)
        roteiro = self.roteiros.pop(0) if self.roteiros else [Evento("texto", "Ok.")]
        yield from roteiro

    def gerar_consulta(self, pergunta, hoje, conversa=None, ancora=None, contexto_local=""):
        self.consultas.append({"pergunta": pergunta, "conversa": conversa, "ancora": ancora,
                               "contexto_local": contexto_local})
        return f"consulta: {ancora + ' ' if ancora else ''}{pergunta}"

    def descarregar(self):
        return True


@pytest.fixture
def athena(tmp_path, monkeypatch):
    cfg = carregar()
    cfg.pasta_dados = tmp_path
    a = nucleo.Athena(cfg)
    a.cerebro = CerebroFalso()
    a.buscas = []

    def executar(nome, args):
        a.buscas.append(dict(args))
        return a.resultado_busca

    a.resultado_busca = RESULTADO_OK
    monkeypatch.setattr(nucleo.fer, "executar", executar)
    return a


def _falar(athena, texto):
    return list(athena.responder(texto))


def _contexto(athena):
    """O [contexto] enviado na última chamada ao modelo."""
    return athena.cerebro.enviadas[-1][-1]["content"] if athena.cerebro.enviadas[-1][-1]["role"] == "user" \
        else next(m["content"] for m in reversed(athena.cerebro.enviadas[-1]) if m["role"] == "user")


# ---------- heurísticas ----------
@pytest.mark.parametrize("texto", [
    "O que você acha do dólar hoje?",
    "Tem certeza que o dólar tá esse valor?",
    "quanto tá o bitcoin agora?",
    "o euro subiu?",
])
def test_cotacao_com_sinal_de_valor_busca(texto):
    assert pede_atualidade(texto)


@pytest.mark.parametrize("texto", [
    "Por que o dólar sobe?",
    "hoje eu queria entender por que o dólar sobe",   # Codex: explicação, não cotação
    "Você ganhou meu carinho",                        # falsos positivos (Codex)
    "Perdeu minha mensagem?",
    "Fiquei doente no dia",
    "Cuidando de você",
])
def test_nao_dispara_busca(texto):
    assert not pede_atualidade(texto)


@pytest.mark.parametrize("texto,esperado", [
    ("Quando?", True), ("e quem ganhou?", True), ("tem certeza?", True), ("onde?", True),
    ("Quando você vai dormir?", False),   # pessoal
    ("valeu", False), ("que legal", False), ("Fiquei doente no dia", False),
    ("quando eu era criança eu adorava futebol e jogava todo dia na rua", False),
])
def test_pergunta_de_seguimento(texto, esperado):
    assert pergunta_de_seguimento(texto) is esperado


def test_eleicao_vai_pra_busca_geral():
    # Notícias olham só a última semana: "quem ganhou as eleições" trouxe análises sem a data.
    assert tipo_de_busca("Sabe me dizer quando e quem ganhou as eleições?") == "geral"
    assert tipo_de_busca("quem ganhou o jogo do flamengo?") == "noticias"


# ---------- núcleo: seguimento ----------
def test_quando_depois_da_busca_busca_de_novo_ancorado(athena):
    _falar(athena, "Sabe me dizer quando e quem ganhou as eleições?")
    _falar(athena, "Quando?")
    assert len(athena.buscas) == 2
    assert athena.cerebro.consultas[-1]["ancora"] == athena.buscas[0]["consulta"]
    assert athena.buscas[1]["tipo"] == "geral"          # data de fato já ocorrido
    assert "mesmo assunto da busca anterior" in _contexto(athena)


def test_quando_sem_busca_anterior_nao_busca(athena):
    _falar(athena, "oi")
    _falar(athena, "Quando?")
    assert athena.buscas == []


@pytest.mark.parametrize("texto", ["valeu", "que legal", "Fiquei doente no dia", "Quando você vai dormir?"])
def test_conversa_depois_da_busca_nao_rebusca(athena, texto):
    _falar(athena, "quem ganhou o último jogo do flamengo?")
    _falar(athena, texto)
    assert len(athena.buscas) == 1


def test_ancora_expira_depois_de_dois_turnos_sem_busca(athena):
    _falar(athena, "quem ganhou o último jogo do flamengo?")
    _falar(athena, "massa")
    _falar(athena, "e você, tá bem")
    _falar(athena, "Quando?")
    assert len(athena.buscas) == 1


def test_limpar_apaga_a_ancora(athena):
    _falar(athena, "quem ganhou o último jogo do flamengo?")
    athena.memoria.limpar()
    _falar(athena, "Quando?")
    assert len(athena.buscas) == 1


def test_tem_certeza_do_dolar_busca_de_novo(athena):
    # "tem certeza?" tem que buscar de novo de propósito (sem cache entre turnos).
    _falar(athena, "O que você acha do dólar hoje?")
    _falar(athena, "Tem certeza que o dólar tá esse valor?")
    assert len(athena.buscas) == 2
    assert "de onde é (o site) e de quando é o valor" in _contexto(athena)


# ---------- núcleo: busca que falha ----------
def test_busca_que_falhou_nao_vira_aviso_de_resultados(athena):
    athena.resultado_busca = RESULTADO_FALHOU
    _falar(athena, "quanto tá o dólar agora?")
    ctx = _contexto(athena).lower()
    assert "não trouxe resultado" in ctx and "não invente" in ctx
    assert "já foi feita uma busca" not in ctx


def test_busca_ok_traz_aviso_normal(athena):
    _falar(athena, "quem ganhou o último jogo do flamengo?")
    assert "já foi feita uma busca" in _contexto(athena)


# ---------- núcleo: mesma busca no mesmo turno ----------
def test_mesma_busca_no_mesmo_turno_reaproveita(athena):
    args = {"consulta": "dólar hoje", "tipo": "geral"}
    athena.cerebro.roteiros = [
        [Evento("ferramentas", [ChamadaFerramenta("buscar_web", args)])],
        [Evento("ferramentas", [ChamadaFerramenta("buscar_web", dict(args))])],
        [Evento("texto", "R$ 5,40 segundo o site X.")],
    ]
    _falar(athena, "me conta uma coisa")
    assert len(athena.buscas) == 1


def test_busca_que_falhou_no_turno_pode_ser_repetida(athena):
    athena.resultado_busca = RESULTADO_FALHOU
    args = {"consulta": "dólar hoje", "tipo": "geral"}
    athena.cerebro.roteiros = [
        [Evento("ferramentas", [ChamadaFerramenta("buscar_web", args)])],
        [Evento("ferramentas", [ChamadaFerramenta("buscar_web", dict(args))])],
        [Evento("texto", "Não consegui achar agora.")],
    ]
    _falar(athena, "me conta uma coisa")
    assert len(athena.buscas) == 2


# ---------- privacidade ----------
def test_consulta_nao_recebe_o_perfil(athena):
    athena.perfil = "- Nome: Fulano Silva; prefere ser chamado de Fulaninho."
    _falar(athena, "quem ganhou o último jogo do flamengo?")
    enviado = json.dumps(athena.cerebro.consultas[-1], ensure_ascii=False)
    assert "Fulano" not in enviado


def test_cidade_so_em_pergunta_que_depende_de_lugar(athena):
    athena.cidade = "Cidade Teste"
    _falar(athena, "quem ganhou o último jogo do flamengo?")
    assert athena.cerebro.consultas[-1]["contexto_local"] == ""
    _falar(athena, "vai chover hoje?")
    assert athena.cerebro.consultas[-1]["contexto_local"] == "Cidade Teste"


@pytest.fixture
def privacidade(monkeypatch):
    """Estado de privacidade isolado por teste, mesmo se o teste falhar (Bob)."""
    monkeypatch.setattr(fer, "_IDENTIFICADORES", frozenset())
    monkeypatch.setattr(fer, "_PEDIDO_ATUAL", "")


def test_buscador_nunca_recebe_nome_dele(monkeypatch, privacidade):
    enviadas = []
    monkeypatch.setattr(fer, "_buscar_com_reserva",
                        lambda c, t: enviadas.append(c) or {"consulta": c, "resultados": []})
    fer.configurar_privacidade(fer.identificadores_do_perfil(
        "- Nome: Fulano Silva Souza; prefere ser chamado de Fulaninho.\n- Bairro: Asa Norte", "Gegê"))
    fer.definir_pedido_atual("quem ganhou o jogo?")
    r = fer.buscar_web("Gegê Fulano Silva placar Flamengo Asa Norte fulano@email.com", "noticias")
    assert enviadas == ["placar Flamengo"]
    assert "obs_privacidade" in r
    # pessoas públicas e sobrenome comum sozinho passam
    fer.buscar_web("Marina Silva ministra", "geral")
    assert enviadas[-1] == "Marina Silva ministra"
    # se ele mesmo pediu pra buscar o próprio nome, passa
    fer.definir_pedido_atual("pesquisa Fulano Silva no google")
    fer.buscar_web("Fulano Silva", "geral")
    assert enviadas[-1] == "Fulano Silva"


def test_consulta_so_com_dado_pessoal_nao_sai(monkeypatch, privacidade):
    monkeypatch.setattr(fer, "_buscar_com_reserva", lambda c, t: pytest.fail("não devia buscar"))
    fer.configurar_privacidade({"fulano"})
    fer.definir_pedido_atual("oi")
    assert "erro" in fer.buscar_web("Fulano", "geral")


def test_email_parecido_com_palavra_do_pedido_nao_passa(privacidade):
    # Bob: com substring, "sto@email.com" passava porque "sto" está em "custo".
    fer.definir_pedido_atual("qual o custo do frete")
    assert fer.proteger_consulta("frete sto@email.com")[0] == "frete"


def test_pedido_com_maiuscula_e_acento_libera_o_proprio_nome(privacidade):
    fer.configurar_privacidade({"gege"})
    fer.definir_pedido_atual("pesquisa GEGÊ no google")
    assert fer.proteger_consulta("Gegê")[0] == "Gegê"
    fer.definir_pedido_atual("placar do jogo")
    assert fer.proteger_consulta("GEGÊ placar")[0] == "placar"


def test_identificadores_ignoram_vazios_e_curtos():
    # Limite de 3 letras de propósito: "ge" apagaria o site "ge" de buscas legítimas (decisão 008).
    ids = fer.identificadores_do_perfil("- Nome: ; \n- Apelidos: Gê, Fufu", "  ")
    assert "" not in ids and "ge" not in ids and "fufu" in ids


# ---------- invariantes ----------
def test_system_continua_identico_e_ontem_so_quando_ele_fala(athena):
    _falar(athena, "Sabe me dizer quando e quem ganhou as eleições?")
    _falar(athena, "Quando?")
    systems = {c[0]["content"] for c in athena.cerebro.enviadas}
    assert len(systems) == 1                       # cache KV
    assert "ontem foi" not in _contexto(athena).lower()
    _falar(athena, "e o jogo de ontem?")
    assert "Ontem foi" in _contexto(athena)


# ---------- regressões da revisão do Codex (decisão 008) ----------
def test_mencionar_dado_pessoal_nao_libera_so_pedir_pra_buscar(privacidade):
    fer.configurar_privacidade({"aninha"})
    fer.definir_pedido_atual("Meu nome é Aninha, mas procura a previsão do tempo")
    assert fer.proteger_consulta("Aninha previsão do tempo")[0] == "previsão do tempo"
    fer.definir_pedido_atual("pesquisa Aninha no google")
    assert fer.proteger_consulta("Aninha")[0] == "Aninha"


def test_endereco_com_virgula_e_bairro_sem_preposicao(monkeypatch, privacidade):
    ids = fer.identificadores_do_perfil("- Endereço: Rua Modelo, 123\n- Bairro: Vila de Esperança", "")
    fer.configurar_privacidade(ids)
    fer.definir_pedido_atual("vai chover?")
    assert fer.proteger_consulta("perto de Rua Modelo, 123")[0] == "perto de"
    # a busca de reserva tira o "de" e recompunha o bairro
    assert fer.proteger_consulta("chuva Vila Esperança")[0] == "chuva"


def test_resultado_vazio_leva_obs_de_falha(monkeypatch, privacidade):
    monkeypatch.setattr(fer, "_buscar_com_reserva", lambda c, t: {"consulta": c, "resultados": []})
    assert fer.buscar_web("algo", "geral")["obs"] == fer.OBS_FALHA


def test_tipo_malformado_do_modelo_nao_quebra_o_turno(athena):
    athena.cerebro.roteiros = [
        [Evento("ferramentas", [ChamadaFerramenta("buscar_web", {"consulta": "x", "tipo": []})])],
        [Evento("texto", "Ok.")],
    ]
    _falar(athena, "me conta uma coisa")
    assert len(athena.buscas) == 1


@pytest.mark.parametrize("texto,esperado", [
    ("Quando chove, fico em casa.", False),   # afirmação
    ("E o horário?", True),
    ("Você tem certeza?", True),
    ("Sério?", False),                        # reação, não pedido de checagem (decisão consciente)
])
def test_seguimento_casos_da_revisao(texto, esperado):
    assert pergunta_de_seguimento(texto) is esperado


def test_ancora_e_a_ultima_busca_do_lote_e_nao_vai_pra_pergunta_completa(athena):
    athena.cerebro.roteiros = [
        [Evento("ferramentas", [ChamadaFerramenta("buscar_web", {"consulta": "Barcelona", "tipo": "noticias"}),
                                ChamadaFerramenta("buscar_web", {"consulta": "Flamengo", "tipo": "noticias"})])],
        [Evento("texto", "Ok.")],
    ]
    _falar(athena, "me conta dos dois times")
    assert athena._ancora_de_busca()["consulta"] == "Flamengo"
    _falar(athena, "Qual o preço do Bitcoin agora?")
    assert athena.cerebro.consultas[-1]["ancora"] is None


@pytest.mark.parametrize("texto,busca,tipo", [
    ("Quem ganhou a Copa de 2014?", True, "geral"),                 # ano passado: não é notícia da semana
    ("Quais são as notícias das eleições hoje?", True, "noticias"),  # pediu notícia
    ("Quem perdeu o carregador?", False, None),
    ("Por que o dólar caiu hoje?", True, None),                      # fato a verificar
    ("Por que a cotação do dólar muda?", False, None),               # explicação
    ("Minha bolsa está na cadeira.", False, None),
])
def test_gatilho_e_tipo_casos_da_revisao(texto, busca, tipo):
    assert pede_atualidade(texto) is busca
    if tipo:
        assert tipo_de_busca(texto) == tipo


def test_tem_certeza_sozinho_busca_de_novo_mesmo_com_a_mesma_consulta(athena):
    # Codex: o teste antigo passava mesmo com cache entre turnos.
    athena.cerebro.gerar_consulta = lambda *a, **k: athena.cerebro.consultas.append(k) or "cotação dólar hoje"
    _falar(athena, "O que você acha do dólar hoje?")
    _falar(athena, "Tem certeza?")
    assert athena.buscas == [{"consulta": "cotação dólar hoje", "tipo": "geral"}] * 2
    assert athena.cerebro.consultas[-1]["ancora"] == "cotação dólar hoje"
