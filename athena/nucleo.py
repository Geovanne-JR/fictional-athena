"""
Núcleo da Athena: junta cérebro, estado emocional, memória e ferramentas.

A interface (terminal hoje; voz e HUD depois) só consome os Eventos que
`responder()` emite. Nada de print aqui dentro — é isso que permite plugar
voz e HUD na Etapa 4/5 sem mexer no núcleo.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterator

from . import ferramentas as fer
from .cerebro import Cerebro, Evento
from .config import Config
from .estado import MotorEmocional, eh_despedida
from .memoria import Diario, MemoriaCurta
from .prompt import (analisar_repeticao, bloco_contexto, dado_volatil, montar_system, pede_atualidade,
                     pede_data, precisa_de_lugar, pergunta_de_seguimento, pergunta_sobre_ela, tipo_de_busca)

MAX_RODADAS_FERRAMENTA = 5  # ex.: buscar → ler página → buscar de novo → ler → responder
TURNOS_DA_ANCORA = 2  # "Quando?" só reaproveita o assunto de uma busca de até 2 turnos atrás

AVISO_BUSCA = (
    "já foi feita uma busca na web com a pergunta dele (resultados abaixo). Responda só com o que "
    "os resultados dizem. 'publicada' é quando a notícia saiu; a data do fato está no texto, contada "
    "a partir da publicação. Nunca repita o 'ontem'/'hoje' escrito na notícia. "
    "'Último' é o mais recente até hoje. "
    "Resultado sem data pode ser página antiga: se usar um, diga de quando é a informação. "
    "Se os resultados não trazem o dado que ele pediu (uma data, um valor), diga que não achou isso; "
    "não deduza nem chute."
)
# Decisão 008: o aviso acima era montado ANTES da busca e afirmava que havia resultados
# mesmo quando ela falhava. Agora o aviso depende do que a busca devolveu.
AVISO_BUSCA_FALHOU = (
    "a primeira busca na web não trouxe resultado. Se você buscar de novo e achar, use só o que achar; "
    "se não, diga que não conseguiu achar. Não invente valores, datas nem fatos, e não diga que viu ou "
    "conferiu nada que não veio."
)
AVISO_SEGUIMENTO = "ele está perguntando sobre o mesmo assunto da busca anterior."
AVISO_VOLATIL = (
    "é um dado que muda (cotação, placar): diga de onde é (o site) e de quando é o valor (horário ou data "
    "que a fonte informa; se ela não informar, diga isso) e, em cotação, a modalidade (comercial, turismo) "
    "só se a fonte disser."
)


class Athena:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cerebro = Cerebro(cfg)
        self.motor = MotorEmocional(cfg.pasta_dados / "estado.json")
        self.memoria = MemoriaCurta(cfg.orcamento_historico)
        self.diario = Diario(cfg.pasta_dados / "conversas")
        self.system = {"role": "system", "content": montar_system(cfg)}
        self.perfil = cfg.arquivo_perfil.read_text(encoding="utf-8")
        self.pensar = cfg.pensar
        self.ferramentas = fer.esquemas() if cfg.ferramentas_ativas else None
        # Privacidade das buscas (decisão 008): o perfil não vai mais pra quem escreve a
        # consulta; só a cidade, e só em pergunta que depende de lugar. E o buscador
        # nunca recebe nome, apelidos ou endereço dele.
        cidade = re.search(r"^\s*[-*]?\s*cidade\s*:\s*(.+)$", self.perfil, re.I | re.M)
        self.cidade = cidade.group(1).strip(" .;") if cidade else ""
        fer.configurar_privacidade(fer.identificadores_do_perfil(self.perfil, cfg.nome_usuario))

    def _ancora_de_busca(self) -> dict | None:
        """Argumentos da última busca nos últimos turnos (consulta escrita por nós, nunca
        trecho de página). Vem da memória curta: /limpar e sessão expirada apagam junto."""
        for turno in reversed(self.memoria.turnos[-TURNOS_DA_ANCORA:]):
            for m in reversed(turno):
                for chamada in reversed(m.get("tool_calls") or []):  # a última do lote (Codex)
                    f = chamada.get("function", {})
                    if f.get("name") == "buscar_web" and (f.get("arguments") or {}).get("consulta"):
                        return f["arguments"]
        return None

    @staticmethod
    def _executar(nome: str, argumentos: dict, ja_buscado: dict) -> str:
        """Mesma busca (consulta + tipo) no mesmo turno reaproveita o resultado, se deu
        certo. Entre turnos não: "tem certeza?" tem que buscar de novo (decisão 008)."""
        if nome != "buscar_web":
            return fer.executar(nome, argumentos)
        # tipo malformado vindo do modelo (ex.: lista) quebrava a chave do dicionário (Codex)
        tipo = "noticias" if argumentos.get("tipo") == "noticias" else "geral"
        chave = (str(argumentos.get("consulta", "")).strip().lower(), tipo)
        if chave in ja_buscado:
            return ja_buscado[chave]
        conteudo = fer.executar(nome, argumentos)
        if not _falhou(conteudo):
            ja_buscado[chave] = conteudo
        return conteudo

    def aquecer(self) -> float:
        return self.cerebro.aquecer(self.system["content"])

    def responder(self, texto: str) -> Iterator[Evento]:
        agora = datetime.now()
        sinais = self.motor.perceber(texto, agora)
        avisos = analisar_repeticao(
            self.memoria.ultimas_respostas(4),
            self.memoria.ultimas_perguntas(4) + [texto],
            self.cfg.temas_vigiados,
        )
        if pergunta_sobre_ela(texto):
            avisos.append(
                "ele perguntou sobre o que você é ou sente: responda em uma ou duas frases, do seu jeito, "
                "no presente, sem filosofar sobre corpo, biologia ou processamento. Se ele perguntou a sério "
                "se você é uma IA, confirme com naturalidade numa frase."
            )
        fer.definir_pedido_atual(texto)  # termo pessoal que ele mesmo pediu pra buscar passa
        ja_buscado: dict = {}
        ancora = self._ancora_de_busca()
        # "Quando?" logo depois de uma busca: busca de novo, ancorada no assunto (decisão 008).
        seguimento = bool(self.ferramentas) and ancora is not None and pergunta_de_seguimento(texto)
        busca_automatica = bool(self.ferramentas) and (pede_atualidade(texto) or seguimento)
        despedida = eh_despedida(texto, ja_conversou=bool(self.memoria.turnos))
        if despedida:
            avisos.append("ele está se despedindo: responda com uma despedida curta e natural.")

        busca_feita: list[dict] = []
        if busca_automatica:
            # O modelo decide mal quando buscar (testado: ignorou o aviso e inventou
            # a versão do Ollama). Então o código busca antes, como se ela tivesse
            # chamado a ferramenta, e ela segue livre pra buscar de novo.
            # O código decide QUANDO buscar; o modelo escreve O QUE buscar.
            # O assunto pode ter vindo da resposta dela ("tem Barcelona amanhã" → "que horas?").
            conversa = [f"ele: {p}" for p in self.memoria.ultimas_perguntas(2)]
            conversa += [f"você: {r[:200]}" for r in self.memoria.ultimas_respostas(1)]
            if seguimento and not pede_atualidade(texto):
                # "Quando?" pede data de algo já falado: busca geral (notícias só olham a semana).
                tipo = "geral" if pede_data(texto) else ancora.get("tipo", "geral")
            else:
                tipo = tipo_de_busca(texto)
            # Âncora só se a pergunta depende do assunto anterior: "Qual o preço do Bitcoin
            # agora?" é completa e recebia "Barcelona" como âncora (Codex).
            depende = seguimento and (not pede_atualidade(texto) or len(texto.split()) <= 4)
            consulta = self.cerebro.gerar_consulta(
                texto, f"{agora:%d/%m/%Y}", conversa,
                ancora=ancora["consulta"] if depende else None,
                contexto_local=self.cidade if precisa_de_lugar(texto) else "",
            )
            args = {"consulta": consulta, "tipo": tipo}
            yield Evento("ferramenta", {"nome": "buscar_web", "argumentos": args})
            chamada = {"role": "assistant", "content": "",
                       "tool_calls": [{"function": {"name": "buscar_web", "arguments": args}}]}
            conteudo = self._executar("buscar_web", args, ja_buscado)
            busca_feita = [chamada, {"role": "tool", "content": conteudo, "tool_name": "buscar_web"}]
            if _falhou(conteudo):
                avisos.append(AVISO_BUSCA_FALHOU)
            else:
                avisos.append(AVISO_BUSCA)
                if seguimento:
                    avisos.append(AVISO_SEGUIMENTO)
                if dado_volatil(texto) or dado_volatil(consulta):
                    avisos.append(AVISO_VOLATIL)
        contexto = bloco_contexto(agora, self.motor.descrever(agora, "o " + self.cfg.nome_usuario), avisos, texto)

        # No histórico fica a mensagem crua; o [contexto] só vai na mensagem atual.
        turno: list[dict] = [{"role": "user", "content": texto}, *busca_feita]
        enviadas: list[dict] = [{"role": "user", "content": f"{contexto}\n\n{texto}"}, *busca_feita]
        resposta_final = ""
        metricas: dict = {}

        repetiu_vazia = False
        for _ in range(MAX_RODADAS_FERRAMENTA + 1):  # +1: a nova tentativa de resposta vazia
            mensagens = [self.system, *self.memoria.mensagens(), *enviadas]
            resposta, chamadas = "", []
            for ev in self.cerebro.conversar(mensagens, self.ferramentas, self.pensar):
                if ev.tipo == "texto":
                    resposta += ev.dado
                    yield ev
                elif ev.tipo == "ferramentas":
                    chamadas = ev.dado
                elif ev.tipo == "metricas":
                    metricas = ev.dado
                else:
                    yield ev

            if not resposta.strip() and not chamadas and not repetiu_vazia:
                # O modelo às vezes encerra sem gerar nada (visto 1 vez em 10 na
                # validação da persona; não reproduzível). Gera de novo uma vez.
                repetiu_vazia = True
                continue

            msg = {"role": "assistant", "content": resposta}
            if chamadas:
                msg["tool_calls"] = [{"function": {"name": c.nome, "arguments": c.argumentos}} for c in chamadas]
            enviadas.append(msg)
            turno.append(msg)
            if not chamadas:
                resposta_final = resposta
                break
            for c in chamadas:
                yield Evento("ferramenta", {"nome": c.nome, "argumentos": c.argumentos})
                resultado = self._executar(c.nome, c.argumentos, ja_buscado)
                m = {"role": "tool", "content": resultado, "tool_name": c.nome}
                enviadas.append(m)
                turno.append(m)

        if metricas:
            yield Evento("metricas", metricas)

        self.memoria.adicionar_turno(turno)
        self.motor.salvar()
        self.diario.registrar(
            usuario=texto,
            athena=resposta_final,
            sinais=sorted(sinais),
            avisos=avisos,
            estado=self.motor.resumo(agora),
            metricas=metricas,
            modelo=self.cerebro.modelo,
        )
        if despedida:
            yield Evento("despedida")

    def dormir(self) -> bool:
        """Salva o estado e libera a VRAM."""
        self.motor.salvar()
        return self.cerebro.descarregar()


def _falhou(conteudo: str) -> bool:
    """Busca com erro ou sem nenhum resultado."""
    try:
        dados = json.loads(conteudo)
    except (TypeError, ValueError):
        return True
    return not isinstance(dados, dict) or "erro" in dados or ("resultados" in dados and not dados["resultados"])
