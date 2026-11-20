from datetime import datetime

from athena.memoria import MemoriaCurta
import pytest

from athena.prompt import analisar_repeticao, bloco_contexto, pede_atualidade, pergunta_sobre_ela, tipo_de_busca


@pytest.mark.parametrize("texto,esperado", [
    ("você tem sentimentos de verdade?", True),
    ("você sente as coisas?", True),
    ("você é uma IA, né?", True),
    ("você é real?", True),
    ("você tem alguma emoção?", True),
    ("você pensa?", True),
    ("você é um robô?", True),                  # revisão do Antigravity: "um" não casava
    ("você é inteligência artificial?", True),
    ("você sentiu falta de mim?", False),       # pergunta pessoal normal, não sobre a natureza dela
    ("você é boa em cálculo?", False),
    ("o que você acha do Rust?", False),
    # falsos positivos apontados na revisão do Antigravity
    ("o que você pensa sobre Rust?", False),
    ("você sente que essa query tá lenta?", False),
    ("o que você e o Gemini acham disso?", False),
])
def test_pergunta_sobre_ela(texto, esperado):
    assert pergunta_sobre_ela(texto) is esperado


@pytest.mark.parametrize("texto", [
    "quem ganhou o último jogo do flamengo?",
    "qual a versão mais recente do ollama?",
    "o que rolou de notícia sobre a UnB essa semana?",
    "quanto tá o dólar?",
    "vai chover hoje em Brasília?",
    "e quando é o próximo jogo?",
    "quando estreia a nova temporada?",
    "quando o Flamengo joga?",                  # revisão do Antigravity
    "quando a nova temporada estreia?",
    # teste pelo celular
    "Quando foi as eleições?",
    "Vai ter jogo do Barcelona?",
    "e o jogo do flamengo?",
    "quando foram as eleições?",
    "quando é o jogo?",
    "tem jogo do Barça hoje?",
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
    "qual o próximo passo do projeto?",
    "quando é melhor usar lista em vez de tupla?",
    "joguei muito ontem",
    # falsos positivos apontados pelo Antigravity
    "quando acontece um deadlock em Python?",
    "bora jogar jogo da velha",
    "tem jogo bom no Steam?",
    "como funciona a eleição de líder no Raft?",
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


def test_sem_aviso_de_pergunta_se_ela_ja_corrigiu():
    # Revisão do Antigravity: o aviso diria "sua última terminou com pergunta", o que seria falso.
    respostas = ["Isso é heap. Quer exemplo?", "Feito. Mais alguma coisa?", "Pronto."]
    avisos = analisar_repeticao(respostas, ["x"], [])
    assert not any("não pergunte" in a for a in avisos)


@pytest.mark.parametrize("resposta", [
    "Gosto sim, mas como eu não tenho ouvidos, minha experiência é técnica.",
    "Faço isso da melhor forma que uma IA pode fazer.",
    "Sinto muito pelo que aconteceu, Gegê.",
    "Segundo os resultados da busca, o jogo foi ontem.",
])
def test_aviso_quando_ela_fala_como_maquina(resposta):
    avisos = analisar_repeticao([resposta], ["x"], [])
    assert any("como máquina" in a for a in avisos)


@pytest.mark.parametrize("resposta", [
    "Eita! Vi agora no ge que o Mengão ganhou de virada.",
    # termos técnicos e honestidade não contam (revisão do Antigravity)
    "Normaliza a base de dados antes de criar o índice.",
    "Um modelo de linguagem é treinado pra prever o próximo token.",
    "Sou uma IA, e você sabe bem, foi você que me montou.",
    "Relaxa, sem pressão, faz no seu tempo.",
])
def test_sem_aviso_de_maquina_em_fala_normal(resposta):
    avisos = analisar_repeticao([resposta], ["x"], [])
    assert not any("como máquina" in a for a in avisos)


def test_deslize_ja_corrigido_nao_gera_aviso_de_novo():
    # Revisão do Antigravity: olhar 2 respostas repetia o aviso de um erro já corrigido.
    respostas = ["Obrigado! Como uma IA, fico feliz.", "Obrigada! Fiquei feliz."]
    avisos = analisar_repeticao(respostas, ["x"], [])
    assert not any("masculino" in a or "máquina" in a for a in avisos)


@pytest.mark.parametrize("texto,tipo", [
    ("quem ganhou o último jogo do flamengo?", "noticias"),
    ("o que rolou de notícia sobre a UnB essa semana?", "noticias"),
    ("qual a versão mais recente do Ollama hoje?", "geral"),   # revisão do Antigravity
    ("quanto tá o dólar hoje?", "geral"),
    # O Antigravity sugeriu "noticias"; ao vivo, o filtro da última semana não achou a
    # data de uma eleição de outubro. Busca geral acha a página do calendário.
    ("quando foi as eleições?", "geral"),
])
def test_tipo_de_busca(texto, tipo):
    assert tipo_de_busca(texto) == tipo


@pytest.mark.parametrize("resposta", [
    "Obrigado! Fiquei feliz com isso.",
    "Hoje tô meio cansado, confesso.",
    "Fiquei curioso com essa ideia.",
    "Estou pronto, manda.",
])
def test_aviso_quando_ela_fala_de_si_no_masculino(resposta):
    avisos = analisar_repeticao([resposta], ["x"], [])
    assert any("masculino" in a for a in avisos)


@pytest.mark.parametrize("resposta", [
    "Obrigada! Fiquei orgulhosa daquela solução.",
    "Você tá cansado? Vai dormir.",          # falando dele
    "Ele tava animado com o jogo.",           # terceira pessoa
    "Tô bem curiosa pra ver isso rodando.",
])
def test_sem_aviso_de_masculino_quando_ok(resposta):
    avisos = analisar_repeticao([resposta], ["x"], [])
    assert not any("masculino" in a for a in avisos)


def test_sem_aviso_quando_ele_puxou_o_tema():
    respostas = ["o Flamengo jogou bem", "o flamengo tá em 1º"]
    avisos = analisar_repeticao(respostas, ["e o flamengo?"], ["flamengo"])
    assert avisos == []


def test_bloco_contexto_tem_dia_e_periodo():
    b = bloco_contexto(datetime(2026, 11, 19, 21, 40), "Você está bem.", [])
    assert "quinta-feira" in b and "21:40" in b and "(noite)" in b


def test_aviso_de_pergunta_ja_depois_de_uma():
    # Teste pelo celular: 4 de 5 respostas terminaram com pergunta.
    avisos = analisar_repeticao(["Massa. E você, tá bem?"], ["x"], [])
    assert any("não pergunte" in a for a in avisos)
    assert not any("não pergunte" in a for a in analisar_repeticao(["Massa."], ["x"], []))


def test_aviso_de_pergunta_no_meio_da_resposta():
    # No celular, avisada, ela trocou o "?" do fim por pergunta no meio (decisão 008).
    avisos = analisar_repeticao(["Que fofo! E você, dormiu? Eu tô bem por aqui."], ["x"], [])
    assert any("não pergunte" in a for a in avisos)
