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
    assert c.gerar_consulta("o que rolou na UnB?", "perfil", "19/11/2026") == \
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
    assert c.gerar_consulta("quem ganhou?", "perfil", "19/11/2026") == "quem ganhou?"


def test_gerar_consulta_ignora_resposta_vazia_ou_gigante():
    assert _cerebro(_ClienteFalso("")).gerar_consulta("x?", "p", "hoje") == "x?"
    assert _cerebro(_ClienteFalso("a" * 500)).gerar_consulta("x?", "p", "hoje") == "x?"
