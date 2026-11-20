import httpx
import pytest

from athena import ferramentas as fer
from athena.config import carregar_env

RESPOSTA = {
    "results": [
        {"title": "Ao vivo: Flamengo x Athletico-PR", "url": "https://a", "content": "pré-jogo",
         "published_date": "Wed, 18 Nov 2026 01:42:40 GMT", "raw_content": "texto a"},
        {"title": "Flamengo vence e vira virtual campeão", "url": "https://b", "content": "venceu por 2 a 1",
         "published_date": "Thu, 19 Nov 2026 11:00:00 GMT", "raw_content": "texto b"},
        {"title": "Clube de Regatas do Flamengo", "url": "https://c", "content": "perfil", "raw_content": None},
    ]
}


class _Resp:
    def __init__(self, dados, status=200):
        self._dados, self.status_code = dados, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=httpx.Request("POST", "https://x"),
                                        response=httpx.Response(self.status_code))

    def json(self):
        return self._dados


@pytest.fixture
def com_chave(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-teste")
    monkeypatch.setattr(fer, "_enriquecer", lambda itens: None)


def test_tavily_normaliza_data_e_ordena_noticias(com_chave, monkeypatch):
    enviado = {}

    def post(url, json, **kw):
        enviado.update(json)
        return _Resp(RESPOSTA)

    monkeypatch.setattr(fer.httpx, "post", post)
    r = fer.buscar_web("último jogo do flamengo", "noticias")
    assert r["fonte_busca"] == "tavily"
    assert enviado["topic"] == "news" and enviado["time_range"] == "week"
    datas = [i.get("data") for i in r["resultados"]]
    # 01:42 GMT de 18/11 = 22:42 de 17/11 em Brasília
    assert datas == ["2026-11-19", "2026-11-17", None]  # mais nova primeiro, sem data no fim
    assert r["resultados"][0]["conteudo"].startswith("<<<TEXTO DA WEB")


def test_texto_vai_pras_noticias_mais_novas_depois_de_ordenar(com_chave, monkeypatch):
    # Achado da revisão do Antigravity: o texto era atribuído antes de ordenar.
    velha = {"title": "velha", "url": "https://v", "content": "", "raw_content": "texto velho",
             "published_date": "Mon, 02 Nov 2026 10:00:00 GMT"}
    nova = {"title": "nova", "url": "https://n", "content": "", "raw_content": "texto novo",
            "published_date": "Thu, 19 Nov 2026 10:00:00 GMT"}
    mais_nova = {"title": "mais nova", "url": "https://m", "content": "", "raw_content": "texto mais novo",
                 "published_date": "Thu, 19 Nov 2026 20:00:00 GMT"}
    monkeypatch.setattr(fer, "LER_AUTOMATICO", 1)
    monkeypatch.setattr(fer.httpx, "post", lambda *a, **k: _Resp({"results": [velha, nova, mais_nova]}))
    itens = fer.buscar_web("x", "noticias")["resultados"]
    assert itens[0]["data"] == "2026-11-19"
    assert "conteudo" in itens[0] and "conteudo" not in itens[-1]


def test_noticias_ampliam_pro_mes_se_semana_vier_vazia(com_chave, monkeypatch):
    periodos = []

    def post(url, json, **kw):
        periodos.append(json["time_range"])
        return _Resp({"results": []} if json["time_range"] == "week" else RESPOSTA)

    monkeypatch.setattr(fer.httpx, "post", post)
    r = fer.buscar_web("algo raro", "noticias")
    assert periodos == ["week", "month"]
    assert len(r["resultados"]) == 3


def test_busca_geral_sem_filtro_de_periodo_nem_pais(com_chave, monkeypatch):
    # "country=brazil" piorava assunto técnico (versão do Ollama); o contexto do
    # Brasil agora vem da consulta escrita pelo modelo ("Universidade de Brasília").
    enviado = {}
    monkeypatch.setattr(fer.httpx, "post", lambda url, json, **kw: enviado.update(json) or _Resp(RESPOSTA))
    fer.buscar_web("versão do ollama", "geral")
    assert enviado["topic"] == "general" and "time_range" not in enviado and "country" not in enviado


def test_sem_creditos_cai_pro_duckduckgo(com_chave, monkeypatch):
    monkeypatch.setattr(fer.httpx, "post", lambda *a, **k: _Resp({}, status=432))
    monkeypatch.setattr(fer, "_buscar", lambda c, t: [{"title": "t", "href": "https://x", "body": "b"}])
    r = fer.buscar_web("algo", "geral")
    assert r["fonte_busca"] == "duckduckgo"


def test_chave_invalida_fica_registrada_e_cai_pro_duckduckgo(com_chave, monkeypatch):
    # Achado da auditoria do Bob: 401/403 não podem passar em silêncio.
    monkeypatch.setattr(fer.httpx, "post", lambda *a, **k: _Resp({}, status=401))
    monkeypatch.setattr(fer, "_buscar", lambda c, t: [{"title": "t", "href": "https://x", "body": "b"}])
    r = fer.buscar_web("algo", "geral")
    assert r["fonte_busca"] == "duckduckgo"
    assert "HTTP 401" in r["obs"]


def test_tavily_com_results_null_cai_pro_duckduckgo(com_chave, monkeypatch):
    # Achado da revisão do Antigravity: TypeError escapava da reserva.
    monkeypatch.setattr(fer.httpx, "post", lambda *a, **k: _Resp({"results": None}))
    monkeypatch.setattr(fer, "_buscar", lambda c, t: [{"title": "t", "href": "https://x", "body": "b"}])
    assert fer.buscar_web("algo", "noticias")["fonte_busca"] == "duckduckgo"


def test_filtro_de_periodo_nao_vaza_entre_chamadas(com_chave, monkeypatch):
    # Achado da auditoria do Bob: o dict do pedido era mutado.
    pedidos = []

    def post(url, json, **kw):
        pedidos.append(dict(json))
        return _Resp({"results": []})

    monkeypatch.setattr(fer.httpx, "post", post)
    fer._buscar_tavily("x", "noticias")
    fer._buscar_tavily("y", "geral")
    assert [p.get("time_range") for p in pedidos] == ["week", "month", None]


def test_sem_chave_nem_tenta_tavily(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(fer, "LER_AUTOMATICO", 0)
    monkeypatch.setattr(fer.httpx, "post", lambda *a, **k: pytest.fail("não devia chamar a Tavily"))
    monkeypatch.setattr(fer, "_buscar", lambda c, t: [{"title": "t", "href": "https://x", "body": "b"}])
    assert fer.buscar_web("algo")["fonte_busca"] == "duckduckgo"


def test_data_iso():
    assert fer._data_iso("Thu, 19 Nov 2026 11:00:00 GMT") == "2026-11-19"
    assert fer._data_iso("2026-11-19T10:00:00") == "2026-11-19"
    assert fer._data_iso(None) == "" and fer._data_iso("ontem") == ""


def test_carregar_env_nao_sobrescreve(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# segredo\nTAVILY_API_KEY="tvly-do-arquivo" # chave da Athena\nBOB_API_KEY=do-bob\n',
                   encoding="utf-8")
    monkeypatch.setenv("TAVILY_API_KEY", "do-sistema")
    monkeypatch.setenv("BOB_API_KEY", "x")
    monkeypatch.delenv("BOB_API_KEY")
    carregar_env(env)
    import os
    assert os.environ["TAVILY_API_KEY"] == "do-sistema"     # não sobrescreve
    assert "BOB_API_KEY" not in os.environ                  # chave de outra ferramenta não entra


def test_carregar_env_le_aspas_e_comentario(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('TAVILY_API_KEY="tvly-do-arquivo" # chave da Athena\n', encoding="utf-8")
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    monkeypatch.delenv("TAVILY_API_KEY")
    carregar_env(env)
    import os
    assert os.environ["TAVILY_API_KEY"] == "tvly-do-arquivo"
