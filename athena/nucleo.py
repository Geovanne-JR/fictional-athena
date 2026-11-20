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
from .estado import MotorEmocional, eh_despedida
from .memoria import Diario, MemoriaCurta
from .prompt import (analisar_repeticao, bloco_contexto, montar_system, pede_atualidade,
                     pergunta_sobre_ela, tipo_de_busca)

MAX_RODADAS_FERRAMENTA = 5  # ex.: buscar → ler página → buscar de novo → ler → responder


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
        busca_automatica = bool(self.ferramentas) and pede_atualidade(texto)
        if busca_automatica:
            avisos.append(
                "já foi feita uma busca na web com a pergunta dele (resultados abaixo). Responda só com o que "
                "os resultados dizem. 'publicada' é quando a notícia saiu; a data do fato está no texto, contada "
                "a partir da publicação. Nunca repita o 'ontem'/'hoje' escrito na notícia. "
                "'Último' é o mais recente até hoje. "
                "Resultado sem data pode ser página antiga: se usar um, diga de quando é a informação. "
                "Se não tiver a resposta, busque de novo com outras palavras ou diga que não encontrou."
            )
        despedida = eh_despedida(texto, ja_conversou=bool(self.memoria.turnos))
        if despedida:
            avisos.append("ele está se despedindo: responda com uma despedida curta e natural.")
        contexto = bloco_contexto(agora, self.motor.descrever(agora, "o " + self.cfg.nome_usuario), avisos)

        # No histórico fica a mensagem crua; o [contexto] só vai na mensagem atual.
        turno: list[dict] = [{"role": "user", "content": texto}]
        enviadas: list[dict] = [{"role": "user", "content": f"{contexto}\n\n{texto}"}]
        resposta_final = ""
        metricas: dict = {}

        if busca_automatica:
            # O modelo decide mal quando buscar (testado: ignorou o aviso e inventou
            # a versão do Ollama). Então o código busca antes, como se ela tivesse
            # chamado a ferramenta, e ela segue livre pra buscar de novo.
            # O código decide QUANDO buscar; o modelo escreve O QUE buscar.
            # O assunto pode ter vindo da resposta dela ("tem Barcelona amanhã" → "que horas?").
            conversa = [f"ele: {p}" for p in self.memoria.ultimas_perguntas(2)]
            conversa += [f"você: {r[:200]}" for r in self.memoria.ultimas_respostas(1)]
            consulta = self.cerebro.gerar_consulta(texto, self.perfil, f"{agora:%d/%m/%Y}", conversa)
            args = {"consulta": consulta, "tipo": tipo_de_busca(texto)}
            yield Evento("ferramenta", {"nome": "buscar_web", "argumentos": args})
            chamada = {"role": "assistant", "content": "",
                       "tool_calls": [{"function": {"name": "buscar_web", "arguments": args}}]}
            resultado = {"role": "tool", "content": fer.executar("buscar_web", args), "tool_name": "buscar_web"}
            enviadas += [chamada, resultado]
            turno += [chamada, resultado]

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
        if despedida:
            yield Evento("despedida")

    def dormir(self) -> bool:
        """Salva o estado e libera a VRAM."""
        self.motor.salvar()
        return self.cerebro.descarregar()
