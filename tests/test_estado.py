from datetime import datetime, timedelta

from athena.estado import MotorEmocional, detectar_sinais, eh_despedida, energia_circadiana


def test_despedidas():
    assert eh_despedida("tchau athena", ja_conversou=False)
    assert eh_despedida("valeu, até amanhã!", ja_conversou=True)
    assert eh_despedida("vou dormir, flw", ja_conversou=True)
    assert eh_despedida("boa noite athena", ja_conversou=True)


def test_nao_e_despedida():
    assert not eh_despedida("boa noite athena", ja_conversou=False)  # cumprimento
    assert not eh_despedida("como se diz tchau em japonês?", ja_conversou=True)
    assert not eh_despedida("me explica heap", ja_conversou=True)
    assert not eh_despedida("falou-se muito sobre isso mas eu ainda quero entender melhor a parte de grafos", True)

NOITE = datetime(2026, 11, 19, 21, 0)


def test_energia_circadiana_tem_picos_e_vale():
    assert energia_circadiana(4) < 0.35
    assert energia_circadiana(10.5) > 0.7
    assert energia_circadiana(21) > 0.7
    assert energia_circadiana(15) < energia_circadiana(10.5)


def test_sinais_em_portugues_com_e_sem_acento():
    assert "estresse" in detectar_sinais("tenho prova amanhã e tô desesperado")
    assert "tristeza" in detectar_sinais("tô mal hoje")
    assert "hostil" in detectar_sinais("athena sua inútil")
    assert "agradecimento" in detectar_sinais("valeu!")
    assert detectar_sinais("me passa o comando do git") == set()


def test_elogio_melhora_humor_e_grosseria_piora():
    m = MotorEmocional()
    base = m.estado.humor
    m.perceber("mandou bem demais", NOITE)
    assert m.estado.humor > base
    m.perceber("sua idiota", NOITE)
    assert m.estado.humor < base
    assert m.estado.clima_usuario == "rispido_com_voce"


def test_irritacao_passa_com_o_tempo():
    m = MotorEmocional()
    m.perceber("ia burra", NOITE)
    irritada = m.estado.humor
    m.decair((NOITE + timedelta(hours=4)).timestamp())
    assert m.estado.humor > irritada
    assert abs(m.estado.humor - 0.25) < 0.05
    assert m.estado.clima_usuario == "neutro"


def test_estresse_desliga_o_humor():
    m = MotorEmocional()
    m.perceber("socorro, prazo da entrega é hoje", NOITE)
    assert m.nivel_de_humor(NOITE) == "nenhum"
    assert "Humor: nenhum" in m.descrever(NOITE)


def test_mensagem_repetida_gasta_paciencia():
    m = MotorEmocional()
    m.perceber("compila aí", NOITE)
    antes = m.estado.paciencia
    s = m.perceber("compila aí", NOITE)
    assert "repetida" in s
    assert m.estado.paciencia < antes


def test_estado_persiste(tmp_path):
    caminho = tmp_path / "estado.json"
    m = MotorEmocional(caminho)
    m.perceber("valeu, genial", NOITE)
    m.salvar()
    m2 = MotorEmocional(caminho)
    assert m2.estado.vinculo == m.estado.vinculo
    assert m2.estado.interacoes == 1
