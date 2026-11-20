"""Testes do núcleo com um cérebro falso (sem Ollama, sem rede)."""
import pytest

from athena import nucleo
from athena.cerebro import ChamadaFerramenta, Evento
from athena.config import carregar


class CerebroFalso:
    """Devolve, a cada chamada de conversar(), o próximo roteiro da fila."""

    def __init__(self, roteiros):
        self.roteiros, self.chamadas, self.modelo = list(roteiros), 0, "falso"

    def conversar(self, mensagens, ferramentas=None, pensar=False):
        self.chamadas += 1
        yield from self.roteiros.pop(0)

    def gerar_consulta(self, pergunta, contexto, hoje):
        return pergunta

    def descarregar(self):
        return True


@pytest.fixture
def athena(tmp_path):
    cfg = carregar()
    cfg.pasta_dados = tmp_path
    return nucleo.Athena(cfg)


def _texto(eventos):
    return "".join(e.dado for e in eventos if e.tipo == "texto")


def test_resposta_vazia_gera_de_novo_uma_vez(athena):
    athena.cerebro = CerebroFalso([[], [Evento("texto", "Oi!")]])
    eventos = list(athena.responder("mandou bem, valeu"))
    assert _texto(eventos) == "Oi!"
    assert athena.cerebro.chamadas == 2
    # o histórico não guarda a tentativa vazia
    assert [m["content"] for m in athena.memoria.mensagens()] == ["mandou bem, valeu", "Oi!"]


def test_resposta_vazia_duas_vezes_nao_entra_em_loop(athena):
    athena.cerebro = CerebroFalso([[], []])
    list(athena.responder("oi"))
    assert athena.cerebro.chamadas == 2


def test_ferramenta_e_depois_resposta(athena, monkeypatch):
    monkeypatch.setattr(nucleo.fer, "executar", lambda nome, args: '{"cpu_uso_pct": 3}')
    athena.cerebro = CerebroFalso([
        [Evento("ferramentas", [ChamadaFerramenta("status_do_pc", {})])],
        [Evento("texto", "Tá de boa, CPU em 3%.")],
    ])
    eventos = list(athena.responder("como tá o pc?"))
    assert [e.dado["nome"] for e in eventos if e.tipo == "ferramenta"] == ["status_do_pc"]
    assert _texto(eventos) == "Tá de boa, CPU em 3%."
    papeis = [m["role"] for m in athena.memoria.mensagens()]
    assert papeis == ["user", "assistant", "tool", "assistant"]


def test_despedida_emite_evento(athena):
    athena.cerebro = CerebroFalso([[Evento("texto", "Boa noite!")]])
    list(athena.responder("e aí"))  # já conversou, então "boa noite" vira despedida
    athena.cerebro = CerebroFalso([[Evento("texto", "Até amanhã!")]])
    assert any(e.tipo == "despedida" for e in athena.responder("boa noite athena"))


def test_contexto_vai_so_na_mensagem_atual(athena):
    vistas = []

    class Espiao(CerebroFalso):
        def conversar(self, mensagens, ferramentas=None, pensar=False):
            vistas.append([m["content"] for m in mensagens])
            yield from super().conversar(mensagens, ferramentas, pensar)

    athena.cerebro = Espiao([[Evento("texto", "um")], [Evento("texto", "dois")]])
    list(athena.responder("primeira"))
    list(athena.responder("segunda"))
    segunda = vistas[1]
    assert segunda[0] == athena.system["content"]          # system estático (cache KV)
    assert segunda[1] == "primeira"                         # histórico sem [contexto]
    assert segunda[-1].startswith("[contexto") and segunda[-1].endswith("segunda")
