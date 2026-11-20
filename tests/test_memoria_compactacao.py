import json

import pytest

from athena.memoria import LIMITE_FERRAMENTA_NO_HISTORICO, MemoriaCurta, compactar_ferramenta


@pytest.mark.parametrize("tamanho", [10, 700], ids=["curto", "longo"])
def test_busca_no_historico_guarda_apenas_referencias(tamanho):
    busca = json.dumps({
        "consulta": "calendário eleitoral",
        "fonte_busca": "tavily",
        "nota_datas": "A publicação foi ontem.",
        "resultados": [
            {
                "titulo": "Calendário eleitoral",
                "url": "https://exemplo.test/noticia",
                "data": "2026-11-19",
                "publicada": "ontem (quinta-feira, 19/11)",
                "trecho": "Abertura da notícia",
                "conteudo": "<<<TEXTO DA WEB>>> " + "x" * tamanho + " <<<FIM DO TEXTO DA WEB>>>",
            },
            {"titulo": "Calendário geral", "url": "https://exemplo.test/calendario", "data": ""},
        ],
    }, ensure_ascii=False)
    assert (len(busca) <= LIMITE_FERRAMENTA_NO_HISTORICO) == (tamanho == 10)

    memoria = MemoriaCurta(orcamento_tokens=2_000)
    resultado = {"role": "tool", "tool_name": "buscar_web", "content": busca}
    memoria.adicionar_turno([resultado])

    guardado = memoria.mensagens()[0]
    assert guardado["tool_name"] == "buscar_web"
    dados = json.loads(guardado["content"])
    assert dados["consulta"] == "calendário eleitoral"
    assert dados["fonte_busca"] == "tavily"
    assert dados["resultados"] == [
        {"titulo": "Calendário eleitoral", "url": "https://exemplo.test/noticia", "publicada_em": "2026-11-19"},
        {"titulo": "Calendário geral", "url": "https://exemplo.test/calendario"},
    ]
    assert "publicação" in dados["obs"] and "fato" in dados["obs"]
    for removido in ('"data"', '"publicada"', '"conteudo"', '"trecho"', "<<<TEXTO DA WEB", "ontem"):
        assert removido not in guardado["content"]
    assert resultado["content"] == busca


@pytest.mark.parametrize("tamanho", [10, 700], ids=["curto", "longo"])
def test_leitura_de_pagina_no_historico_guarda_so_url_e_obs(tamanho):
    url = "https://exemplo.test/pagina"
    pagina = json.dumps({
        "url": url,
        "texto": "<<<TEXTO DA WEB>>> " + "x" * tamanho + " <<<FIM DO TEXTO DA WEB>>>",
        "cortado": False,
    })

    dados = json.loads(compactar_ferramenta(pagina))
    assert dados == {"url": url, "obs": "texto da página omitido no histórico"}


def test_erro_curto_continua_legivel():
    erro = {"erro": "não consegui extrair texto"}
    assert json.loads(compactar_ferramenta(json.dumps(erro))) == erro


def test_erro_longo_e_abreviado_em_json_valido():
    erro = {"erro": "busca indisponível " + "x" * 700}
    dados = json.loads(compactar_ferramenta(json.dumps(erro)))
    assert dados["erro"].startswith("busca indisponível ")
    assert dados["erro"].endswith("…")
    assert len(dados["erro"]) <= LIMITE_FERRAMENTA_NO_HISTORICO


def test_turno_sem_ferramenta_fica_intacto():
    memoria = MemoriaCurta(orcamento_tokens=100)
    turno = [
        {"role": "user", "content": "tudo bem?"},
        {"role": "assistant", "content": "Tudo bem por aqui."},
    ]

    memoria.adicionar_turno(turno)

    assert memoria.mensagens() == turno
