"""Datas relativas: o código faz a conta, o modelo não (decisão 007)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from athena import ferramentas as fer
from athena.prompt import bloco_contexto

HOJE = date(2026, 11, 20)  # sexta-feira


@pytest.mark.parametrize("data,esperado", [
    ("2026-11-20", "hoje (sexta-feira, 20/11)"),
    ("2026-11-19", "ontem (quinta-feira, 19/11)"),
    ("2026-11-18", "anteontem (quarta-feira, 18/11)"),   # o caso real: ela disse "ontem"
    ("2026-11-15", "há 5 dias (domingo, 15/11)"),
    ("2026-11-10", "semana passada (terça-feira, 10/11)"),
    ("2026-10-20", "há 4 semanas (terça-feira, 20/10)"),
    ("2026-06-01", "há 5 meses (segunda-feira, 01/06)"),
    ("2026-11-25", "data futura (quarta-feira, 25/11)"),
    ("lixo", ""),
])
def test_quando(data, esperado):
    assert fer.quando(data, HOJE) == esperado


def test_marcar_quando_so_nos_datados():
    r = {"resultados": [{"titulo": "a", "data": "2026-11-18"}, {"titulo": "b"}]}
    fer.marcar_quando(r, HOJE)
    assert r["resultados"][0]["publicada"].startswith("anteontem")
    assert "publicada" not in r["resultados"][1]
    assert "fato" in r["nota_datas"]


def test_marcar_quando_sem_datas_nao_poe_nota():
    r = fer.marcar_quando({"resultados": [{"titulo": "b"}]}, HOJE)
    assert "nota_datas" not in r


def test_buscar_web_sai_com_data_de_publicacao(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(fer, "_enriquecer", lambda itens: None)
    hoje = date.today().isoformat()
    monkeypatch.setattr(fer, "_buscar", lambda c, t: [
        {"title": "t", "url": "https://x", "body": "b", "date": hoje + "T10:00:00"}])
    r = fer.buscar_web("flamengo", "noticias")
    assert r["resultados"][0]["publicada"].startswith("hoje")


def test_contexto_diz_qual_foi_ontem_depois_da_meia_noite():
    # O caso real: 00:30 de sexta, 20/11. "Ontem" é quinta, 19/11.
    b = bloco_contexto(datetime(2026, 11, 20, 0, 30), "Você está bem.", [])
    assert "sexta-feira, 20/11/2026" in b
    assert "Ontem foi quinta-feira, 19/11." in b


def test_contexto_vira_o_mes():
    b = bloco_contexto(datetime(2026, 12, 1, 9, 0), "ok", [])
    assert "Ontem foi segunda-feira, 30/11." in b


BRASILIA = timezone(timedelta(hours=-3))


def test_data_de_publicacao_no_fuso_de_brasilia(monkeypatch):
    # Caso real: "Thu, 19 Nov 2026 01:27:52 GMT" é 22h27 de quarta, 18/11, em Brasília.
    monkeypatch.setattr(fer, "FUSO", BRASILIA)
    assert fer._data_iso("Thu, 19 Nov 2026 01:27:52 GMT") == "2026-11-18"
    assert fer._data_iso("Thu, 19 Nov 2026 14:00:00 GMT") == "2026-11-19"
    assert fer._data_iso("2026-11-19T01:00:00") == "2026-11-19"  # sem fuso: fica como veio


def test_data_iso_8601_com_fuso_do_duckduckgo():
    # Revisão do Antigravity: ISO com fuso caía no corte cru [:10] e ficava em UTC.
    assert fer._data_iso("2026-11-19T01:27:52+00:00") == "2026-11-18"
    assert fer._data_iso("2026-11-19T01:27:52Z") == "2026-11-18"


def test_duckduckgo_usa_o_mesmo_fuso():
    itens = fer.normalizar_resultados(
        [{"title": "t", "url": "u", "body": "b", "date": "2026-11-19T01:27:52+00:00"}], "noticias")
    assert itens[0]["data"] == "2026-11-18"


def test_quando_poe_o_ano_se_nao_for_este():
    assert fer.quando("2024-11-20", HOJE) == "há 2 anos (quarta-feira, 20/11/2024)"
    assert fer.quando("2025-11-01", HOJE) == "há 1 ano (sábado, 01/11/2025)"
    assert fer.quando("2025-12-20", HOJE) == "há 11 meses (sábado, 20/12/2025)"
