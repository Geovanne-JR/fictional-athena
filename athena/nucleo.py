"""
Núcleo da Athena: junta cérebro, estado emocional, memória e ferramentas.

A interface (terminal hoje; voz e HUD depois) só consome os Eventos que
`responder()` emite. Nada de print aqui dentro — é isso que permite plugar
voz e HUD na Etapa 4/5 sem mexer no núcleo.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from . import ferramentas as fer
from .cerebro import Cerebro, Evento
from .config import Config
from .estado import MotorEmocional
from .memoria import Diario, MemoriaCurta
from .prompt import analisar_repeticao, bloco_contexto, montar_system

MAX_RODADAS_FERRAMENTA = 4


class Athena:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cerebro = Cerebro(cfg)
        self.motor = MotorEmocional(cfg.pasta_dados / "estado.json")
        self.memoria = MemoriaCurta(cfg.orcamento_historico)
        self.diario = Diario(cfg.pasta_dados / "conversas")
        self.system = {"role": "system", "content": montar_system(cfg)}
        self.pensar = cfg.pensar
        self.ferramentas = fer.esquemas() if cfg.ferramentas_ativas else None

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
        contexto = bloco_contexto(agora, self.motor.descrever(agora, "o " + self.cfg.nome_usuario), avisos)

        # No histórico fica a mensagem crua; o [contexto] só vai na mensagem atual.
        turno: list[dict] = [{"role": "user", "content": texto}]
        enviadas: list[dict] = [{"role": "user", "content": f"{contexto}\n\n{texto}"}]
        resposta_final = ""
        metricas: dict = {}

        for _ in range(MAX_RODADAS_FERRAMENTA):
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

            msg = {"role": "assistant", "content": resposta}
            if chamadas:
                msg["tool_calls"] = [{"function": {"name": c.nome, "arguments": c.argumentos}} for c in chamadas]
            enviadas.append(msg)
            turno.append(msg)
            if not chamadas:
                resposta_final = resposta
                break
            for c in chamadas:
                yield Evento("ferramenta", c.nome)
                resultado = fer.executar(c.nome, c.argumentos)
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
