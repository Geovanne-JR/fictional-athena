"""Servidor da Etapa 2.5a, offline: cérebro falso, sem Ollama, sem rede (decisão 007)."""
import threading
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from athena import nucleo, servidor
from athena.cerebro import Evento
from athena.config import carregar
from athena.instancia import AthenaJaRodando, TravaDeInstancia

TOKEN = "token-de-teste-com-tamanho-bom"
HOSTS = ["testserver", "127.0.0.1", "localhost", "pc.tail1234.ts.net"]
BEARER = {"Authorization": f"Bearer {TOKEN}"}


class CerebroFalso:
    modelo = "falso"

    def __init__(self, resposta="Oi, Gegê!", espera=0.0):
        self.resposta, self.espera, self.descarregou = resposta, espera, 0

    def conversar(self, mensagens, ferramentas=None, pensar=False):
        time.sleep(self.espera)
        yield Evento("texto", self.resposta)
        yield Evento("metricas", {"primeira_palavra_s": 0.1, "tokens_por_s": 30})

    def gerar_consulta(self, pergunta, contexto, hoje):
        return pergunta

    def descarregar(self):
        self.descarregou += 1
        return True

    def aquecer(self, system):
        return 0.0


@pytest.fixture
def athena(tmp_path):
    cfg = carregar()
    cfg.pasta_dados = tmp_path
    cfg.ferramentas_ativas = False
    a = nucleo.Athena(cfg)
    a.cerebro = CerebroFalso()
    return a


@pytest.fixture
def cliente(athena):
    app = servidor.criar_app(athena, TOKEN, HOSTS, aquecer=False)
    with TestClient(app) as c:
        yield c


def _conversa(ws, texto):
    ws.send_json({"tipo": "mensagem", "texto": texto})
    eventos = []
    while True:
        ev = ws.receive_json()
        eventos.append(ev)
        if ev["tipo"] in ("fim", "ocupada"):
            return eventos


# ---------- página e cabeçalhos ----------
def test_pagina_abre_sem_login_e_tem_csp(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "Athena" in r.text
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "unsafe-inline" not in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_so_serve_a_lista_fechada_de_arquivos(cliente):
    assert cliente.get("/app.js").status_code == 200
    for caminho in ("/web/index.html", "/../.env", "/%2e%2e/.env", "/servidor.py"):
        assert cliente.get(caminho).status_code == 404


def test_sem_documentacao_automatica(cliente):
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404


def test_host_estranho_e_recusado(cliente):
    # DNS rebinding: um site malicioso apontando o próprio domínio pro 127.0.0.1.
    r = cliente.get("/api/historico", headers={**BEARER, "Host": "malicioso.com"})
    assert r.status_code == 400


# ---------- autenticação ----------
def test_api_exige_login(cliente):
    assert cliente.get("/api/historico").status_code == 401
    assert cliente.get("/api/estado").status_code == 401
    assert cliente.get("/api/historico", headers={"Authorization": "Bearer errado"}).status_code == 401


def test_bearer_funciona_pro_app_kotlin(cliente):
    r = cliente.get("/api/estado", headers=BEARER)
    assert r.status_code == 200 and r.json()["modelo"] == "falso"


def test_entrar_da_cookie_seguro(cliente):
    r = cliente.post("/api/entrar", json={"token": TOKEN})
    assert r.status_code == 204
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "secure" in cookie
    assert TOKEN.lower() not in cookie  # o cookie é derivado, não o token
    cliente.cookies.set(servidor.COOKIE, servidor.valor_do_cookie(TOKEN))
    assert cliente.get("/api/historico").status_code == 200


def test_entrar_com_token_errado(cliente):
    assert cliente.post("/api/entrar", json={"token": "chute"}).status_code == 401
    assert cliente.post("/api/entrar", content=b"lixo").status_code == 401


def test_entrar_de_outro_site_e_recusado(cliente):
    r = cliente.post("/api/entrar", json={"token": TOKEN}, headers={"Origin": "https://malicioso.com"})
    assert r.status_code == 403


def test_token_curto_nao_sobe(athena):
    with pytest.raises(ValueError):
        servidor.criar_app(athena, "curto", HOSTS)


# ---------- WebSocket ----------
def test_ws_sem_login_e_recusado(cliente):
    with pytest.raises(WebSocketDisconnect):
        with cliente.websocket_connect("/ws") as ws:
            ws.receive_json()


def test_ws_token_na_url_nao_vale(cliente):
    with pytest.raises(WebSocketDisconnect):
        with cliente.websocket_connect(f"/ws?token={TOKEN}") as ws:
            ws.receive_json()


def test_ws_de_outro_site_e_recusado_mesmo_com_login(cliente):
    # Sequestro de WebSocket: página maliciosa usando o cookie do Gegê.
    with pytest.raises(WebSocketDisconnect):
        with cliente.websocket_connect("/ws", headers={**BEARER, "Origin": "https://malicioso.com"}) as ws:
            ws.receive_json()


def test_ws_conversa_em_streaming(cliente, athena):
    with cliente.websocket_connect("/ws", headers={**BEARER, "Origin": "https://pc.tail1234.ts.net"}) as ws:
        assert ws.receive_json()["tipo"] == "pronta"
        ws.send_json({"tipo": "ping"})
        assert ws.receive_json() == {"tipo": "pong"}
        eventos = _conversa(ws, "oi")
    tipos = [e["tipo"] for e in eventos]
    assert tipos == ["inicio", "texto", "metricas", "fim"]
    assert eventos[1]["dado"] == "Oi, Gegê!"
    h = cliente.get("/api/historico", headers=BEARER).json()["mensagens"]
    assert h == [{"de": "voce", "texto": "oi"}, {"de": "athena", "texto": "Oi, Gegê!"}]


def test_ws_ignora_lixo_e_mensagem_vazia(cliente):
    with cliente.websocket_connect("/ws", headers=BEARER) as ws:
        ws.receive_json()
        ws.send_text("não é json")
        ws.send_json(["lista"])
        ws.send_json({"tipo": "mensagem", "texto": "   "})
        ws.send_json({"tipo": "ping"})
        assert ws.receive_json() == {"tipo": "pong"}  # nada antes do pong


def test_ws_ocupada_quando_ja_esta_respondendo(cliente, athena):
    servico = cliente.app.state.servico
    servico.trava.acquire()  # simula o terminal/outro aparelho no meio de uma resposta
    try:
        with cliente.websocket_connect("/ws", headers=BEARER) as ws:
            ws.receive_json()
            assert _conversa(ws, "oi")[-1]["tipo"] == "ocupada"
    finally:
        servico.trava.release()


# ---------- ciclo de vida ----------
def _esperar_trava(servico, limite=3.0):
    fim = time.monotonic() + limite
    while servico.ocupada and time.monotonic() < fim:
        time.sleep(0.01)
    assert not servico.ocupada


def test_celular_caiu_no_meio_a_resposta_termina_e_fica_na_memoria(athena):
    athena.cerebro = CerebroFalso("resposta inteira", espera=0.2)
    servico = servidor.Servico(athena, 30)
    assert servico.iniciar_resposta("oi", lambda ev: None)  # ninguém ouvindo
    assert servico.ocupada
    _esperar_trava(servico)
    assert servico.historico()[-1] == {"de": "athena", "texto": "resposta inteira"}


def test_erro_no_nucleo_libera_a_trava(athena):
    def quebra(*a, **k):
        raise ConnectionError("ollama caiu")
        yield  # noqa: gerador

    athena.cerebro.conversar = quebra
    servico = servidor.Servico(athena, 30)
    eventos = []
    servico.iniciar_resposta("oi", eventos.append)
    _esperar_trava(servico)
    assert eventos[-2]["tipo"] == "erro" and "ollama" not in eventos[-2]["dado"].lower()
    assert eventos[-1] is None


def test_sessao_expira_depois_de_muito_tempo_parado(athena):
    agora = [1000.0]
    servico = servidor.Servico(athena, sessao_minutos=30, relogio=lambda: agora[0])
    servico.iniciar_resposta("primeira", lambda ev: None)
    _esperar_trava(servico)
    agora[0] += 29 * 60
    servico.iniciar_resposta("segunda", lambda ev: None)
    _esperar_trava(servico)
    assert len(servico.historico()) == 4
    agora[0] += 31 * 60
    servico.iniciar_resposta("terceira", lambda ev: None)
    _esperar_trava(servico)
    assert [m["texto"] for m in servico.historico()][0] == "terceira"


def test_despedida_libera_vram_e_comeca_conversa_nova(athena):
    servico = servidor.Servico(athena, 30)
    servico.iniciar_resposta("oi", lambda ev: None)
    _esperar_trava(servico)
    servico.iniciar_resposta("boa noite, tchau", lambda ev: None)
    _esperar_trava(servico)
    assert athena.cerebro.descarregou == 1
    assert servico.historico() == []


def test_desligar_o_servidor_libera_vram(athena):
    app = servidor.criar_app(athena, TOKEN, HOSTS, aquecer=False)
    with TestClient(app):
        pass
    assert athena.cerebro.descarregou == 1


def test_limpar(cliente):
    with cliente.websocket_connect("/ws", headers=BEARER) as ws:
        ws.receive_json()
        _conversa(ws, "oi")
    assert cliente.post("/api/limpar", headers={**BEARER, "Origin": "https://malicioso.com"}).status_code == 403
    assert cliente.post("/api/limpar").status_code == 401  # sem login (Bob)
    assert cliente.post("/api/limpar", headers=BEARER).status_code == 204
    assert cliente.get("/api/historico", headers=BEARER).json()["mensagens"] == []


# ---------- utilidades ----------
@pytest.mark.parametrize("origem,ok", [
    (None, True),                                  # app Kotlin / curl
    ("https://pc.tail1234.ts.net", True),
    ("http://127.0.0.1:8765", True),
    ("https://outro-pc.tail1234.ts.net", False),   # outra máquina da tailnet (ou Funnel alheio)
    ("https://pc.tail1234.ts.net.malicioso.com", False),
    ("null", False),
])
def test_origem_permitida(origem, ok):
    assert servidor.origem_permitida(origem, HOSTS) is ok


def test_gerar_token_nao_duplica_e_preserva_o_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TAVILY_API_KEY=tvly-x", encoding="utf-8")  # sem \n no fim
    assert servidor.gerar_token(env) is True
    assert servidor.gerar_token(env) is False
    linhas = env.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "TAVILY_API_KEY=tvly-x"
    tokens = [l for l in linhas if l.startswith("ATHENA_TOKEN=")]
    assert len(tokens) == 1 and len(tokens[0].split("=", 1)[1]) >= 24


def test_so_uma_athena_por_vez(tmp_path):
    with TravaDeInstancia(tmp_path):
        with pytest.raises(AthenaJaRodando):
            with TravaDeInstancia(tmp_path):
                pass
    with TravaDeInstancia(tmp_path):  # liberou ao sair
        pass


def test_uvicorn_consegue_falar_websocket():
    # O TestClient não usa o uvicorn: sem a biblioteca `websockets`, todos os
    # testes passavam e o servidor real recusava o /ws (pego no teste ao vivo).
    import uvicorn.protocols.websockets.websockets_impl  # noqa: F401


def test_csp_nao_repete_host_recusado(cliente):
    r = cliente.get("/", headers={"Host": "malicioso.com"})
    assert r.status_code == 400
    assert "malicioso" not in r.headers.get("content-security-policy", "")


@pytest.mark.parametrize("nome,esperado", [
    ("meu-pc.tail0000.ts.net.", "meu-pc.tail0000.ts.net"),
    ("*.ts.net", None),
    ("evil.com", None),
    ("", None),
])
def test_nome_tailscale_validado(monkeypatch, nome, esperado):
    import json, subprocess
    saida = subprocess.CompletedProcess([], 0, stdout=json.dumps({"Self": {"DNSName": nome}}))
    monkeypatch.setattr(servidor.subprocess, "run", lambda *a, **k: saida)
    assert servidor.nome_tailscale() == esperado


def test_historico_some_quando_a_sessao_expirou(athena):
    # Revisão do Antigravity: a tela mostrava uma conversa que ela já tinha esquecido.
    agora = [1000.0]
    servico = servidor.Servico(athena, sessao_minutos=30, relogio=lambda: agora[0])
    servico.iniciar_resposta("oi", lambda ev: None)
    _esperar_trava(servico)
    assert len(servico.historico()) == 2
    agora[0] += 31 * 60
    assert servico.historico() == []


def test_resposta_espera_o_aquecimento(athena):
    # Revisão do Antigravity: aquecer e responder ao mesmo tempo no Ollama.
    servico = servidor.Servico(athena, 30)
    servico._aquecendo.acquire()  # aquecimento em andamento
    servico.iniciar_resposta("oi", lambda ev: None)
    time.sleep(0.2)
    assert servico.historico() == []  # ainda esperando
    servico._aquecendo.release()
    _esperar_trava(servico)
    assert len(servico.historico()) == 2


def test_sair_apaga_o_cookie_com_as_mesmas_flags(cliente):
    cookie = cliente.post("/api/sair").headers["set-cookie"].lower()
    assert "max-age=0" in cookie and "secure" in cookie and "samesite=strict" in cookie
