"""Servidor da Athena (Etapa 2.5a): a mesma Athena do terminal, pelo navegador.

O núcleo não muda: este módulo só repassa os Eventos de `Athena.responder()`
por WebSocket. A API (rotas /api e /ws) não depende da página: o futuro app
Kotlin usa as mesmas rotas, autenticando com `Authorization: Bearer <token>`.

Segurança (decisão 007):
- escuta só em 127.0.0.1; quem publica na rede privada é o Tailscale Serve
  (HTTPS). Nenhuma porta é aberta no roteador nem na rede local;
- só aceita os hosts exatos deste PC (bloqueia DNS rebinding);
- token do .env (ATHENA_TOKEN). O navegador troca o token por um cookie
  HttpOnly + SameSite=Strict; o token nunca vai na URL;
- WebSocket: autenticação e Origin checados ANTES de aceitar a conexão;
- a página mostra o texto dela como texto puro (texto da web pode trazer HTML).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .nucleo import Athena

ENDERECO = "127.0.0.1"  # fixo de propósito: nunca 0.0.0.0
COOKIE = "athena_sessao"
COOKIE_DIAS = 30
MAX_TEXTO = 4000  # caracteres por mensagem
MAX_FRAME_WS = 64 * 1024  # bytes; o padrão do uvicorn é 16 MB (achado da auditoria do Bob)
TAMANHO_MIN_TOKEN = 16
WEB = Path(__file__).parent / "web"
ARQUIVOS_WEB = {  # rota → (arquivo, tipo). Lista fechada: nada de servir pasta.
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/estilo.css": ("estilo.css", "text/css; charset=utf-8"),
    "/icone.svg": ("icone.svg", "image/svg+xml"),
}

log = logging.getLogger("athena.servidor")


def valor_do_cookie(token: str) -> str:
    """Derivado do token: trocar o token no .env invalida os cookies antigos."""
    return hmac.new(token.encode(), b"athena-sessao-web-v1", hashlib.sha256).hexdigest()


def autenticado(cabecalhos, cookies, token: str) -> bool:
    auth = cabecalhos.get("authorization", "")
    if auth.startswith("Bearer ") and hmac.compare_digest(auth[7:].strip().encode(), token.encode()):
        return True
    cookie = cookies.get(COOKIE, "")
    return bool(cookie) and hmac.compare_digest(cookie.encode(), valor_do_cookie(token).encode())


def origem_permitida(origem: str | None, hosts: list[str]) -> bool:
    """Sem Origin: cliente que não é navegador (app Kotlin, curl). Com Origin:
    tem que ser uma página deste servidor. Bloqueia site malicioso aberto no
    navegador usando a sessão do Gegê (CSRF / sequestro de WebSocket)."""
    if not origem:
        return True
    return (urlparse(origem).hostname or "").lower() in hosts


def nome_tailscale() -> str | None:
    """Nome MagicDNS deste PC (ex.: 'pc-do-gege.tail1234.ts.net'), ou None."""
    exe = shutil.which("tailscale") or r"C:\Program Files\Tailscale\tailscale.exe"
    try:
        saida = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, timeout=5)
        nome = json.loads(saida.stdout).get("Self", {}).get("DNSName", "")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    nome = nome.rstrip(".").lower()
    # Vai direto pra lista de hosts aceitos: nada de curinga nem nome estranho (Bob).
    return nome if re.fullmatch(r"[a-z0-9-]+\.[a-z0-9-]+\.ts\.net", nome) else None


class Servico:
    """Uma Athena, uma GPU: uma resposta por vez. A trava é liberada pela
    thread que gera a resposta, então o celular cair no meio não a prende."""

    def __init__(self, athena: Athena, sessao_minutos: int, relogio: Callable[[], float] = time.monotonic):
        self.athena = athena
        self.sessao_s = sessao_minutos * 60
        self.relogio = relogio
        self.trava = threading.Lock()
        self.ultima_atividade: float | None = None
        self._aquecendo = threading.Lock()

    @property
    def ocupada(self) -> bool:
        return self.trava.locked()

    def iniciar_resposta(self, texto: str, entregar: Callable[[dict | None], None]) -> bool:
        """Começa a responder numa thread. `entregar` recebe cada evento (dict)
        e None no fim. Devolve False se ela já estiver respondendo."""
        if not self.trava.acquire(blocking=False):
            return False
        threading.Thread(target=self._responder, args=(texto, entregar), daemon=True).start()
        return True

    def expirar_se_parada(self) -> None:
        """Muito tempo sem mensagem: conversa nova. Chamada antes de responder E
        antes de mostrar o histórico, senão a tela mostrava uma conversa que ela
        já tinha esquecido (revisão do Antigravity)."""
        if self.ultima_atividade is not None and self.relogio() - self.ultima_atividade > self.sessao_s:
            self.athena.memoria.limpar()
            self.ultima_atividade = None

    def _responder(self, texto: str, entregar: Callable[[dict | None], None]) -> None:
        try:
            with self._aquecendo:  # se a página acabou de abrir, espera o aquecimento (Antigravity)
                pass
            self.expirar_se_parada()
            despedida = False
            for ev in self.athena.responder(texto):
                despedida = despedida or ev.tipo == "despedida"
                entregar({"tipo": ev.tipo, "dado": ev.dado})
            if despedida:
                # Como no terminal: despediu, libera a VRAM e a próxima conversa é nova.
                self.athena.memoria.limpar()
                self.athena.dormir()
        except Exception:
            log.exception("erro ao responder")
            entregar({"tipo": "erro", "dado": "Deu um problema aqui do meu lado. Tenta de novo?"})
        finally:
            self.ultima_atividade = self.relogio()
            self.trava.release()
            entregar(None)

    def aquecer_em_segundo_plano(self) -> None:
        """Abriu a página: já carrega o modelo. Se ninguém falar nada, o
        keep_alive de 5 min do Ollama devolve a VRAM sozinho."""
        if self.ocupada or not self._aquecendo.acquire(blocking=False):
            return

        def tarefa():
            try:
                self.athena.aquecer()
            except Exception:
                log.warning("não consegui aquecer o modelo (Ollama fechado?)")
            finally:
                self._aquecendo.release()

        threading.Thread(target=tarefa, daemon=True).start()

    def historico(self) -> list[dict]:
        if not self.ocupada:
            self.expirar_se_parada()
        nome = {"user": "voce", "assistant": "athena"}
        turnos = list(self.athena.memoria.turnos)  # cópia: a thread da resposta pode mexer na lista
        return [{"de": nome[m["role"]], "texto": m["content"]}
                for t in turnos for m in t
                if m["role"] in nome and m.get("content")]


def criar_app(athena: Athena, token: str, hosts: list[str], sessao_minutos: int = 30,
              aquecer: bool = True) -> FastAPI:
    if len(token) < TAMANHO_MIN_TOKEN:
        raise ValueError("ATHENA_TOKEN curto demais")
    hosts = [h.lower() for h in hosts]
    servico = Servico(athena, sessao_minutos)

    @asynccontextmanager
    async def ciclo(app):
        yield
        await asyncio.to_thread(athena.dormir)  # servidor desligando: libera a VRAM

    app = FastAPI(title="Athena", docs_url=None, redoc_url=None, openapi_url=None, lifespan=ciclo)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    app.state.servico = servico

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request: Request, chamar_proximo):
        resp = await chamar_proximo(request)
        # Este middleware roda ANTES do TrustedHost: só põe o host no CSP se for
        # um dos permitidos (achado da auditoria do Bob).
        host = request.headers.get("host", "")
        ws_ok = f" wss://{host} ws://{host}" if host.split(":")[0].lower() in hosts else ""
        resp.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
            f"manifest-src 'self'; connect-src 'self'{ws_ok}; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def exigir_login(request: Request) -> JSONResponse | None:
        if not autenticado(request.headers, request.cookies, token):
            return JSONResponse({"erro": "não autenticado"}, status_code=401)
        return None

    def exigir_origem(request: Request) -> JSONResponse | None:
        if not origem_permitida(request.headers.get("origin"), hosts):
            return JSONResponse({"erro": "origem não permitida"}, status_code=403)
        return None

    for rota, (arquivo, tipo) in ARQUIVOS_WEB.items():
        def servir(arquivo=arquivo, tipo=tipo):
            return FileResponse(WEB / arquivo, media_type=tipo)
        app.add_api_route(rota, servir, methods=["GET"], include_in_schema=False)

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifesto():
        return JSONResponse({
            "name": "Athena", "short_name": "Athena", "start_url": "/", "display": "standalone",
            "background_color": "#0d0f14", "theme_color": "#0d0f14",
            "icons": [{"src": "/icone.svg", "sizes": "any", "type": "image/svg+xml"}],
        }, media_type="application/manifest+json")

    @app.post("/api/entrar")
    async def entrar(request: Request):
        if erro := exigir_origem(request):
            return erro
        try:
            enviado = str((await request.json()).get("token", ""))
        except (ValueError, AttributeError):
            enviado = ""
        if not hmac.compare_digest(enviado.encode(), token.encode()):
            await asyncio.sleep(1)  # freia tentativa em série
            return JSONResponse({"erro": "token errado"}, status_code=401)
        resp = Response(status_code=204)
        resp.set_cookie(COOKIE, valor_do_cookie(token), max_age=COOKIE_DIAS * 86400,
                        httponly=True, secure=True, samesite="strict", path="/")
        return resp

    @app.post("/api/sair")
    def sair(request: Request):
        if erro := exigir_origem(request):
            return erro
        resp = Response(status_code=204)
        resp.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        return resp

    @app.get("/api/estado")
    def estado(request: Request):
        if erro := exigir_login(request):
            return erro
        return {"nome": athena.cfg.nome_usuario, "modelo": athena.cerebro.modelo,
                "ocupada": servico.ocupada, "estado": athena.motor.resumo()}

    @app.get("/api/historico")
    def historico(request: Request):
        if erro := exigir_login(request):
            return erro
        return {"mensagens": servico.historico(), "ocupada": servico.ocupada}

    @app.post("/api/limpar")
    def limpar(request: Request):
        if erro := exigir_origem(request) or exigir_login(request):
            return erro
        if not servico.trava.acquire(blocking=False):
            return JSONResponse({"erro": "ocupada"}, status_code=409)
        try:
            athena.memoria.limpar()
        finally:
            servico.trava.release()
        return Response(status_code=204)

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        # Checado no pedido de conexão, antes do accept: quem não passa leva
        # 403 e não ocupa nada (sugestão da auditoria do Bob).
        if not (origem_permitida(websocket.headers.get("origin"), hosts)
                and autenticado(websocket.headers, websocket.cookies, token)):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        if aquecer:
            servico.aquecer_em_segundo_plano()
        await websocket.send_json({"tipo": "pronta", "dado": {"ocupada": servico.ocupada}})
        loop = asyncio.get_running_loop()
        try:
            while True:
                try:
                    msg = json.loads(await websocket.receive_text())
                except ValueError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("tipo") == "ping":
                    await websocket.send_json({"tipo": "pong"})
                    continue
                texto = str(msg.get("texto", "")).strip()[:MAX_TEXTO]
                if msg.get("tipo") != "mensagem" or not texto:
                    continue
                fila: asyncio.Queue = asyncio.Queue()

                def entregar(ev, fila=fila):
                    try:
                        loop.call_soon_threadsafe(fila.put_nowait, ev)
                    except RuntimeError:
                        pass  # servidor desligando

                if not servico.iniciar_resposta(texto, entregar):
                    await websocket.send_json({"tipo": "ocupada"})
                    continue
                await websocket.send_json({"tipo": "inicio"})
                while (ev := await fila.get()) is not None:
                    await websocket.send_text(json.dumps(ev, ensure_ascii=False, default=str))
                await websocket.send_json({"tipo": "fim"})
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass  # celular caiu: a resposta em andamento termina sozinha e fica na memória

    return app


def gerar_token(arquivo_env: Path) -> bool:
    """Cria ATHENA_TOKEN no .env se ainda não existir. Não imprime o token."""
    import secrets
    atual = arquivo_env.read_text(encoding="utf-8-sig") if arquivo_env.exists() else ""
    if any(l.strip().startswith("ATHENA_TOKEN=") for l in atual.splitlines()):
        return False
    sep = "" if not atual or atual.endswith("\n") else "\n"
    with open(arquivo_env, "a", encoding="utf-8") as f:
        f.write(f"{sep}# Senha do servidor da Athena (python -m athena --servidor)\n"
                f"ATHENA_TOKEN={secrets.token_urlsafe(24)}\n")
    return True


def rodar_servidor(athena: Athena) -> None:
    import uvicorn

    token = os.environ.get("ATHENA_TOKEN", "")
    if len(token) < TAMANHO_MIN_TOKEN:
        print("Falta o ATHENA_TOKEN no .env. Rode: python -m athena --gerar-token")
        return
    try:
        athena.cerebro.modelo_instalado()
    except Exception:
        print(f"Não consegui falar com o Ollama em {athena.cfg.host}. Abra o app Ollama e tente de novo.")
        return

    hosts = ["127.0.0.1", "localhost"]
    nome = nome_tailscale()
    if nome:
        hosts.append(nome)
    porta = athena.cfg.porta_servidor
    print(f"Athena ouvindo em http://127.0.0.1:{porta}")
    if nome:
        print(f"No celular (Tailscale): https://{nome}")
        print(f"  publique uma vez com: tailscale serve --bg {porta}")
        print("  use sempre o nome (https://...ts.net), não o IP 100.x: o login só funciona em HTTPS")
    else:
        print("Tailscale não encontrado ou desconectado: só dá pra acessar deste PC.")
    print("Ctrl+C pra desligar (a VRAM é liberada).")
    try:
        uvicorn.run(criar_app(athena, token, hosts, athena.cfg.sessao_minutos),
                    host=ENDERECO, port=porta, log_level="warning", server_header=False,
                    ws_max_size=MAX_FRAME_WS)
    finally:
        athena.dormir()  # porta ocupada, erro no boot, Ctrl+C duplo: a VRAM sai mesmo assim
