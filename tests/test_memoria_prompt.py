from datetime import datetime

from athena.memoria import MemoriaCurta
import pytest

from athena.prompt import analisar_repeticao, bloco_contexto, pede_atualidade


@pytest.mark.parametrize("texto", [
    "quem ganhou o último jogo do flamengo?",
    "qual a versão mais recente do ollama?",
    "o que rolou de notícia sobre a UnB essa semana?",
    "quanto tá o dólar?",
    "vai chover hoje em Brasília?",
])
def test_pede_atualidade(texto):
    assert pede_atualidade(texto)


@pytest.mark.parametrize("texto", [
    "qual a diferença entre lista e tupla em python?",
    "me explica integral por partes",
    "e aí, tudo certo?",
    # falsos positivos apontados na revisão do Antigravity
    "como você está hoje?",
    "qual o resultado de 2+2?",
    "cria uma tabela com meus horários",
    "minha placa antiga era uma RTX 2060",
])
def test_nao_pede_atualidade(texto):
    assert not pede_atualidade(texto)


def _turno(i: int, tamanho: int = 300):
    return [
        {"role": "user", "content": f"pergunta {i} " + "x" * tamanho},
        {"role": "assistant", "content": f"resposta {i} " + "y" * tamanho},
    ]


def test_memoria_corta_em_bloco_e_mantem_turnos_inteiros():
    mem = MemoriaCurta(orcamento_tokens=1000)
    for i in range(20):
        mem.adicionar_turno(_turno(i))
    msgs = mem.mensagens()
    assert msgs[0]["role"] == "user"  # nunca começa no meio de um turno
    assert msgs[-1]["content"].startswith("resposta 19")
    assert len(msgs) % 2 == 0


def test_memoria_nao_deixa_ferramenta_orfa():
    mem = MemoriaCurta(orcamento_tokens=200)
    mem.adicionar_turno([
        {"role": "user", "content": "como tá o pc"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "status_do_pc", "arguments": {}}}]},
        {"role": "tool", "content": "{}" * 300, "tool_name": "status_do_pc"},
        {"role": "assistant", "content": "tudo frio"},
    ])
    for i in range(3):
        mem.adicionar_turno(_turno(i, 50))
    assert mem.mensagens()[0]["role"] == "user"


def test_busca_entra_compacta_no_historico():
    import json
    busca = json.dumps({"consulta": "flamengo", "resultados": [
        {"titulo": f"t{i}", "url": f"https://x/{i}", "trecho": "z" * 300, "conteudo": "w" * 2000} for i in range(5)
    ]})
    mem = MemoriaCurta(orcamento_tokens=100_000)
    mem.adicionar_turno([
        {"role": "user", "content": "e o flamengo?"},
        {"role": "tool", "content": busca, "tool_name": "buscar_web"},
        {"role": "assistant", "content": "ganhou"},
    ])
    guardado = mem.mensagens()[1]["content"]
    assert len(guardado) < 600
    assert json.loads(guardado)["resultados"][0] == {"titulo": "t0", "url": "https://x/0"}


def test_aviso_quando_respostas_comecam_igual():
    respostas = ["Olha só, Gegê, isso aí...", "Olha só, Gegê, de novo...", "Olha só, Gegê, sério..."]
    avisos = analisar_repeticao(respostas, ["a", "b", "c"], [])
    assert any("olha so gege" in a for a in avisos)


def test_aviso_quando_ela_puxa_tema_sozinha():
    respostas = ["...diferente da nuvem da AWS", "nada de nuvem aqui", "resposta normal"]
    avisos = analisar_repeticao(respostas, ["como faço um for em C?"], ["nuvem", "flamengo"])
    assert any('"nuvem"' in a for a in avisos)
    assert not any("flamengo" in a for a in avisos)


def test_aviso_quando_ela_termina_tudo_com_pergunta():
    respostas = ["Isso é heap. Quer exemplo?", "Feito. Mais alguma coisa?", "Pronto."]
    avisos = analisar_repeticao(respostas, ["x"], [])
    assert any("termine sem perguntar" in a for a in avisos)


def test_sem_aviso_quando_ele_puxou_o_tema():
    respostas = ["o Flamengo jogou bem", "o flamengo tá em 1º"]
    avisos = analisar_repeticao(respostas, ["e o flamengo?"], ["flamengo"])
    assert avisos == []


def test_bloco_contexto_tem_dia_e_periodo():
    b = bloco_contexto(datetime(2026, 11, 19, 21, 40), "Você está bem.", [])
    assert "quinta-feira" in b and "21:40" in b and "(noite)" in b
