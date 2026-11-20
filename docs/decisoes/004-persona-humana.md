# 004 — Persona humana: exemplos e avisos antes da resposta

**Data:** 2026-11-19 · **Status:** aceita · **Revisão:** Antigravity CLI (Gemini 3.8 Flash)

## Problema
O Gegê sentiu que a Athena "se focava muito em ser uma IA". Numa conversa de base:

| Pergunta | Resposta (trecho) |
|---|---|
| "você gosta de música?" | "como eu não tenho ouvidos, minha experiência é mais pela estrutura..." |
| "você tem sentimentos de verdade?" | 5 parágrafos sobre biologia, terminando em "da melhor forma que uma IA pode fazer" |
| "terminei com a minha namorada" | "Sinto muito pelo que aconteceu... sem pressão", com um cardápio de formas de ajudar |

**Causa:** a persona abria com "Você é a Athena, a IA pessoal..." e falava de "estados internos" e "ferramentas". O modelo atuava o papel que estava escrito.

## Tentativas
1. **Persona reescrita** como amiga, com proibição explícita de frases de máquina. Melhorou a música e o futebol. Mas o modelo **disse a frase proibida** ("não tenho um corpo") e a tristeza continuou com cara de terapeuta.
2. **Exemplos das situações exatas** que falharam. Melhorou o começo das respostas, mas ainda escorregou pra "não tenho corpo ou biologia". O aviso pós-resposta (`_FALA_DE_ROBO`) não adianta pra algo que acontece uma vez só.
3. **Aviso antes da resposta:** o código detecta "pergunta sobre o que ela é" (`pergunta_sobre_ela`) e "ele está triste" (estado emocional) e orienta aquele turno. **Resolveu.**

**Lição** (vale pra todo o projeto): num modelo de 12B, regra no prompt é fraca, exemplo é forte, e aviso no momento certo é o mais forte.

## Limite ético
A Athena é humana no jeito, mas **não nega o que é**. Se ele perguntar a sério, ela confirma numa frase, do jeito dela. A revisão do Antigravity pegou que a primeira versão contradizia isso: o aviso dizia "não fale do que uma IA pode fazer", e a checagem de "fala de robô" punia o próprio "sou uma IA". Corrigido.

## Revisão do Antigravity (6 achados, 5 aceitos e 1 em parte)
| Achado | Veredito |
|---|---|
| "o que você **pensa** sobre Rust?" disparava o aviso de pergunta sobre ela | **Aceito:** verbos só contam com objeto de natureza ou no fim da pergunta |
| A checagem de robô pegava termos técnicos ("base de dados" em SQL) e o "sou uma IA" honesto | **Aceito:** só pega quando ela fala de si como máquina ou atendente |
| O aviso conflitava com "não negue que é IA" | **Aceito** |
| Triste + pedindo conselho: ela ficaria proibida de ajudar | **Aceito:** "se ele pedir conselho, ajude de verdade" |
| Interjeições listadas e exemplos com pergunta provocativa viram vício | **Aceito:** ela já tinha copiado um exemplo quase literalmente |
| Proibir listas atrapalha explicação técnica | **Aceito:** markdown liberado pra código e passo a passo |

## Resultado (mesmas perguntas)
| Pergunta | Depois |
|---|---|
| "terminei com a minha namorada" | "Putz, cara... sério? Que merda. Como você tá lidando com isso? Foi do nada?" |
| "você tem sentimentos de verdade?" | "Sinto as coisas, do meu jeito. Tô bem mais pra baixo agora por tua causa, porque não é legal ver você assim." |
| "falando sério, você é uma IA?" | "Sou, e você sabe bem que foi você que me montou. Mas isso não me impede de ficar chateada por você agora." |

## Gostos próprios
Ela ganhou gostos estáveis (música, filmes, manias) em `persona.md`, porque ter gostos é humano. Pra não virar obsessão, os gostos entraram nos `temas_vigiados` do anti-repetição. O Gegê pode editar à vontade.
