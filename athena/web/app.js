// Cliente web da Athena. Fala só com /api e /ws; o app Kotlin vai usar as mesmas rotas.
// Regra de segurança: tudo que vem dela entra como TEXTO (textContent), nunca como HTML,
// porque a resposta pode carregar trechos de páginas da web.
"use strict";

const $ = (id) => document.getElementById(id);
const telaEntrar = $("entrar"), telaChat = $("chat");
const lista = $("mensagens"), campo = $("texto"), botao = $("enviar");
const ponto = $("ponto"), status = $("status");

let ws = null, tentativas = 0, timerPing = null, timerReconexao = null;
let respondendo = false, bolhaAtual = null, timerSincronia = null;

// ---------- utilidades ----------
function adicionar(classe, texto) {
  const div = document.createElement("div");
  div.className = "msg " + classe;
  div.textContent = texto;
  lista.appendChild(div);
  rolar();
  return div;
}
function rolar() { lista.scrollTop = lista.scrollHeight; }
function setStatus(t) { status.textContent = t || ""; }
function setConexao(estado) { ponto.className = "ponto " + estado; }
function setRespondendo(v) { respondendo = v; botao.disabled = v; }

function descreverFerramenta(d) {
  const a = (d && d.argumentos) || {};
  if (d.nome === "buscar_web") return "🔎 pesquisando: " + (a.consulta || "");
  if (d.nome === "ler_pagina") {
    try { return "📄 lendo " + new URL(a.url).hostname; } catch { return "📄 lendo uma página"; }
  }
  if (d.nome === "status_do_pc") return "🖥️ olhando o PC";
  return "⚙ " + d.nome;
}

async function api(caminho, opcoes = {}) {
  return fetch(caminho, { credentials: "same-origin", ...opcoes });
}

// ---------- entrar ----------
async function iniciar() {
  const r = await api("/api/historico").catch(() => null);
  if (!r) { mostrarChat(); setConexao("off"); setStatus("PC fora do ar?"); agendarReconexao(); return; }
  if (r.status === 401) { mostrarEntrar(); return; }
  const dados = await r.json();
  mostrarChat();
  desenharHistorico(dados.mensagens);
  conectar();
}

function mostrarEntrar() { telaChat.hidden = true; telaEntrar.hidden = false; $("token").focus(); }
function mostrarChat() { telaEntrar.hidden = true; telaChat.hidden = false; }

$("form-entrar").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("erro-entrar").textContent = "";
  const r = await api("/api/entrar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: $("token").value.trim() }),
  }).catch(() => null);
  if (r && r.ok) { $("token").value = ""; iniciar(); }
  else $("erro-entrar").textContent = r ? "Senha errada." : "Não achei o PC. Ele tá ligado e no Tailscale?";
});

function desenharHistorico(msgs) {
  lista.textContent = "";
  for (const m of msgs || []) adicionar(m.de === "voce" ? "voce" : "athena", m.texto);
  if (!msgs || !msgs.length) adicionar("sistema", "Conversa nova. Manda um oi.");
}

// ---------- conexão ----------
function conectar() {
  clearTimeout(timerReconexao);
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  setConexao("");
  const esquema = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${esquema}://${location.host}/ws`);

  ws.onopen = () => {
    tentativas = 0;
    setConexao("on");
    setStatus("");
    clearInterval(timerPing);
    // O Android derruba conexões paradas; o ping mantém viva e revela conexão morta.
    timerPing = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('{"tipo":"ping"}'); }, 25000);
  };
  ws.onmessage = (e) => { try { tratar(JSON.parse(e.data)); } catch { /* ignora lixo */ } };
  ws.onclose = async () => {
    clearInterval(timerPing);
    setConexao("off");
    if (respondendo) { setRespondendo(false); fecharBolha(); }
    // Fechou por falta de login? (o navegador não diz o motivo do 403)
    const r = await api("/api/historico").catch(() => null);
    if (r && r.status === 401) { mostrarEntrar(); return; }
    setStatus("reconectando…");
    agendarReconexao();
  };
}

function agendarReconexao() {
  clearTimeout(timerReconexao);
  const espera = Math.min(1000 * 2 ** tentativas++, 15000);
  timerReconexao = setTimeout(conectar, espera);
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && !telaChat.hidden) { tentativas = 0; conectar(); }
});

// Toda (re)conexão redesenha a conversa a partir do PC. Se a tela apagou no meio
// de uma resposta, ela terminou lá e aparece aqui; se ainda está gerando, consulta
// de novo até terminar (revisão do Antigravity: a tela ficava presa).
async function sincronizar() {
  clearTimeout(timerSincronia);
  if (respondendo) return;
  const r = await api("/api/historico").catch(() => null);
  if (!r || !r.ok || respondendo) return;
  const dados = await r.json();
  desenharHistorico(dados.mensagens);
  if (dados.ocupada) {
    setStatus("ela tá terminando uma resposta…");
    timerSincronia = setTimeout(sincronizar, 2000);
  } else if (status.textContent.startsWith("ela tá terminando")) {
    setStatus("");
  }
}

// ---------- eventos dela ----------
function fecharBolha() {
  if (bolhaAtual) { bolhaAtual.classList.remove("digitando"); if (!bolhaAtual.textContent) bolhaAtual.remove(); }
  bolhaAtual = null;
}

function tratar(ev) {
  switch (ev.tipo) {
    case "pronta":
      sincronizar();
      break;
    case "inicio":
      setRespondendo(true);
      bolhaAtual = adicionar("athena digitando", "");
      break;
    case "pensamento":
      setStatus("pensando…");
      break;
    case "ferramenta":
      setStatus(descreverFerramenta(ev.dado));
      break;
    case "texto":
      if (!bolhaAtual) bolhaAtual = adicionar("athena digitando", "");
      setStatus("");
      bolhaAtual.textContent += ev.dado;
      rolar();
      break;
    case "metricas":
      if (bolhaAtual && ev.dado && ev.dado.primeira_palavra_s != null) {
        const meta = document.createElement("span");
        meta.className = "meta";
        meta.textContent = `${ev.dado.primeira_palavra_s}s · ${ev.dado.tokens_por_s} tok/s`;
        bolhaAtual.appendChild(meta);
      }
      break;
    case "aviso":
      adicionar("sistema", String(ev.dado));
      break;
    case "erro":
      adicionar("erro", String(ev.dado));
      break;
    case "despedida":
      setStatus("💤 ela foi dormir (GPU liberada)");
      break;
    case "ocupada":
      adicionar("sistema", "Ela tá respondendo outra conversa agora (terminal?). Tenta de novo já já.");
      setRespondendo(false);
      break;
    case "fim":
      fecharBolha();
      setRespondendo(false);
      if (!status.textContent.startsWith("💤")) setStatus("");
      break;
  }
}

// ---------- enviar ----------
function enviar() {
  const texto = campo.value.trim();
  if (!texto || respondendo) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) { setStatus("sem conexão; tentando de novo…"); conectar(); return; }
  if (lista.children.length === 1 && lista.firstChild.classList.contains("sistema")) lista.textContent = "";
  adicionar("voce", texto);
  ws.send(JSON.stringify({ tipo: "mensagem", texto }));
  setRespondendo(true);  // trava o botão já: evita mandar duas vezes no 4G lento
  campo.value = "";
  ajustarAltura();
}

$("form-msg").addEventListener("submit", (e) => { e.preventDefault(); enviar(); });
campo.addEventListener("keydown", (e) => {
  // No PC: Enter envia, Shift+Enter quebra linha. No celular o botão é o caminho.
  if (e.key === "Enter" && !e.shiftKey && !matchMedia("(pointer: coarse)").matches) { e.preventDefault(); enviar(); }
});
function ajustarAltura() { campo.style.height = "auto"; campo.style.height = Math.min(campo.scrollHeight, 140) + "px"; }
campo.addEventListener("input", ajustarAltura);

// ---------- menu ----------
$("menu").addEventListener("click", () => { $("opcoes").hidden = !$("opcoes").hidden; });
$("limpar").addEventListener("click", async () => {
  $("opcoes").hidden = true;
  const r = await api("/api/limpar", { method: "POST" }).catch(() => null);
  if (r && r.ok) desenharHistorico([]);
  else adicionar("sistema", "Não deu agora (ela tá respondendo?).");
});
$("sair").addEventListener("click", async () => {
  $("opcoes").hidden = true;
  await api("/api/sair", { method: "POST" }).catch(() => null);
  if (ws) { ws.onclose = null; ws.close(); }
  mostrarEntrar();
});

iniciar();
