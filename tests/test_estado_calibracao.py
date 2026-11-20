import json
from datetime import datetime, timedelta

from athena.estado import MotorEmocional


MADRUGADA = datetime(2026, 11, 20, 4, 5)
NOITE = datetime(2026, 11, 20, 21)


def test_perguntas_banais_nao_acumulam_curiosidade():
    motor = MotorEmocional()

    for minuto in range(10):
        agora = NOITE + timedelta(minutes=minuto)
        assert "curioso" not in motor.perceber("tudo bem?", agora)

    assert motor.estado.curiosidade <= 0.6
    assert "interessada na conversa" not in motor.descrever(agora)
    assert "bem curiosa com o assunto" not in motor.descrever(agora)


def test_pergunta_com_sinal_de_conteudo_aumenta_curiosidade():
    motor = MotorEmocional()
    antes = motor.estado.curiosidade

    assert "curioso" in motor.perceber("como funciona X?", NOITE)
    assert motor.estado.curiosidade > antes

    motor.perceber("o que você acha disso?", NOITE + timedelta(minutes=1))
    assert "interessada na conversa" in motor.descrever(NOITE + timedelta(minutes=1))


def test_madrugada_mantem_humor_discreto():
    motor = MotorEmocional()
    motor.perceber("mandou bem", MADRUGADA)

    assert motor.energia(MADRUGADA) < 0.35
    assert motor.nivel_de_humor(MADRUGADA) == "discreto"

    # Às 04h05 a curva dá 0,308. Às 03h20 ela cruza o antigo corte de 0,3.
    menor_energia = MADRUGADA.replace(hour=3, minute=20)
    assert motor.energia(menor_energia) < 0.3
    assert motor.nivel_de_humor(menor_energia) == "discreto"


def test_acolhimento_so_no_turno_com_sinal_de_tristeza():
    motor = MotorEmocional()
    acolhimento = "Acolha como amiga numa frase curta"
    motor.perceber("fiquei triste", NOITE)
    descricao = motor.descrever(NOITE)
    assert acolhimento in descricao
    assert "querendo saber o que houve" not in descricao
    assert "Sem oferta de ajuda nem convite a desabafar." in descricao
    assert descricao.count("desabaf") == 1
    assert motor.nivel_de_humor(NOITE) == "nenhum"

    seguinte = NOITE + timedelta(minutes=1)
    motor.perceber("quanto tá o dólar?", seguinte)
    descricao = motor.descrever(seguinte)
    assert acolhimento not in descricao
    assert "querendo saber o que houve" not in descricao
    assert "desabaf" not in descricao
    assert "Siga o assunto dele com leveza, sem reabrir o tema." in descricao
    assert motor.nivel_de_humor(seguinte) == "nenhum"

    nova_tristeza = NOITE + timedelta(minutes=2)
    motor.perceber("fiquei triste de novo. Quanto tá o dólar?", nova_tristeza)
    descricao = motor.descrever(nova_tristeza)
    assert acolhimento in descricao
    assert "responda ao pedido em seguida" in descricao

    depois = nova_tristeza + timedelta(minutes=21)
    motor.perceber("tudo bem?", depois)
    assert "pra baixo" not in motor.descrever(depois)
    assert motor.nivel_de_humor(depois) == "discreto"


def test_estado_antigo_carrega_e_mantem_formato(tmp_path):
    caminho = tmp_path / "estado.json"
    dados = {
        "humor": 0.1,
        "paciencia": 0.7,
        "curiosidade": 0.5,
        "vinculo": 0.4,
        "clima_usuario": "triste",
        "clima_ate": (NOITE + timedelta(minutes=10)).timestamp(),
        "interacoes": 50,
        "atualizado_em": NOITE.timestamp(),
    }
    caminho.write_text(json.dumps(dados), encoding="utf-8")

    motor = MotorEmocional(caminho)
    assert motor.estado.vinculo == 0.4
    assert motor.estado.interacoes == 50
    assert motor.nivel_de_humor(NOITE) == "nenhum"
    assert "sem reabrir o tema" in motor.descrever(NOITE)

    motor.salvar()
    assert json.loads(caminho.read_text(encoding="utf-8")) == dados
