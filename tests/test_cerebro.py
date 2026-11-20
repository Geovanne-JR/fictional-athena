from types import SimpleNamespace

import pytest

from athena.cerebro import Cerebro, extrair_consulta
from athena.config import carregar


class _ClienteFalso:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.chamadas = resposta, erro, []

    def chat(self, **kw):
        self.chamadas.append(kw)
        if self.erro:
            raise self.erro
        return SimpleNamespace(message=SimpleNamespace(content=self.resposta))


def _cerebro(cliente):
    c = Cerebro(carregar())
    c.cliente = cliente
    return c


def test_gerar_consulta_usa_resposta_do_modelo():
    cli = _ClienteFalso('"notícias Universidade de Brasília UnB novembro 2026"\nexplicação extra')
    c = _cerebro(cli)
    assert c.gerar_consulta("o que rolou na UnB?", "19/11/2026") == \
        "notícias Universidade de Brasília UnB novembro 2026"
    assert cli.chamadas[0]["options"]["num_predict"] == 40


@pytest.mark.parametrize("resposta", [
    "Aqui está a consulta:\nplacar último jogo Flamengo",
    "```\nplacar último jogo Flamengo\n```",
    "<think>hmm</think>placar último jogo Flamengo",
    "Consulta: placar último jogo Flamengo",
    "**placar último jogo Flamengo**",
])
def test_extrair_consulta_ignora_enfeites(resposta):
    assert extrair_consulta(resposta) == "placar último jogo Flamengo"


def test_uso_de_gpu_reconhece_tag_latest():
    # Revisão do Antigravity: "--modelo qwen3.5" aparece no ps() como "qwen3.5:latest".
    modelo_ps = SimpleNamespace(model="qwen3.5:latest", name="qwen3.5:latest", size=100, size_vram=100)
    cli = SimpleNamespace(ps=lambda: SimpleNamespace(models=[modelo_ps]))
    c = _cerebro(cli)
    c.modelo = "qwen3.5"
    assert c.uso_de_gpu() == 1.0


def test_gerar_consulta_cai_pra_pergunta_se_der_erro():
    c = _cerebro(_ClienteFalso(erro=ConnectionError("ollama caiu")))
    assert c.gerar_consulta("quem ganhou?", "19/11/2026") == "quem ganhou?"


def test_gerar_consulta_ignora_resposta_vazia_ou_gigante():
    assert _cerebro(_ClienteFalso("")).gerar_consulta("x?", "hoje") == "x?"
    assert _cerebro(_ClienteFalso("a" * 500)).gerar_consulta("x?", "hoje") == "x?"


def test_gerar_consulta_ve_a_conversa():
    # Teste pelo celular: "próximo jogo" depois de "Barcelona" virou busca do Flamengo.
    cli = _ClienteFalso("próximo jogo Barcelona")
    _cerebro(cli).gerar_consulta("qual a data do próximo jogo?", "20/11/2026", ["Vai ter jogo do Barcelona?"])
    enviado = cli.chamadas[0]["messages"][1]["content"]
    assert "Barcelona" in enviado and "próximo jogo" in enviado
    assert "use o assunto da conversa" in cli.chamadas[0]["messages"][0]["content"]


def test_gerar_consulta_com_erro_devolve_a_pergunta_limpa():
    # Revisão do Antigravity: o fallback mandava o texto com a conversa pro buscador.
    c = _cerebro(_ClienteFalso(erro=ConnectionError("caiu")))
    assert c.gerar_consulta("quando é o jogo?", "hoje", ["ele: e o Barcelona?"]) == "quando é o jogo?"
    # Seguimento: "Quando?" puro não serve pro buscador; a reserva leva a âncora (Codex, decisão 008).
    assert c.gerar_consulta("Quando?", "hoje", ["ele: x"], ancora="eleições Brasil 2026") == \
        "eleições Brasil 2026 Quando?"


@pytest.mark.parametrize("resposta,conversa,esperado", [
    # Reteste da decisão 008: "quem ganhou as eleições?" virou "eleições EUA 2024" em 2026.
    ("eleições presidenciais 2024 resultado", None, "eleições presidenciais resultado"),
    ("eleições presidenciais 2026 resultado", None, "eleições presidenciais 2026 resultado"),  # ano de hoje
    ("copa do mundo 2014 final", ["ele: e a copa de 2014?"], "copa do mundo 2014 final"),       # ele citou
])
def test_ano_que_ninguem_citou_sai_da_consulta(resposta, conversa, esperado):
    c = _cerebro(_ClienteFalso(resposta))
    assert c.gerar_consulta("quem ganhou?", "20/11/2026", conversa) == esperado


def test_consulta_assume_brasil_e_nao_ve_perfil():
    cli = _ClienteFalso("eleições Brasil 2026")
    _cerebro(cli).gerar_consulta("quem ganhou as eleições?", "20/11/2026")
    system = cli.chamadas[0]["messages"][0]["content"]
    assert "mora no Brasil" in system
    # system estático: a data vai na mensagem, não no system
    assert "20/11/2026" not in system and "20/11/2026" in cli.chamadas[0]["messages"][1]["content"]


@pytest.mark.parametrize("resposta,conversa,esperado", [
    # Codex: ano colado em pontuação/data passava, e ano dito só pela Athena autorizava.
    ("eleições EUA (2024), resultado", None, "eleições EUA resultado"),
    ("eleição 03/11/2024 resultado", None, "eleição resultado"),
    ("eleição 2024 resultado", ["você: a de 2024 foi diferente"], "eleição resultado"),
    ("eleição 2024 resultado", ["ele: e a de 2024?"], "eleição 2024 resultado"),
])
def test_filtro_de_ano_pega_pontuacao_e_so_aceita_ano_dele(resposta, conversa, esperado):
    assert _cerebro(_ClienteFalso(resposta)).gerar_consulta("e aí?", "20/11/2026", conversa) == esperado
