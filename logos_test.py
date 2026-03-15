"""
logos_test.py — Projeto L.O.G.O.S.
=====================================
Logical Observation & Generative Output Synthesis

Teste de Popper-Turing Lógico para o KOSMOS Agent.
Baseado na proposta do Kosmos Supreme para hardware restrito (i5 2a gen).

O que testa:
    1. Identificação de contradição entre estudos reais
    2. Formulação de hipótese parcimoniosa e falsificável
    3. Design de experimento de baixo custo
    4. Resistência ao viés de concordância (sycophancy)
    5. Coerência lógica sob contexto mínimo

Por que funciona no i5 2a gen:
    - Contexto pequeno (~800 tokens de input)
    - Output limitado a 300 palavras
    - Máxima exigência de abstração, mínima de RAM

Uso:
    cd D:\\FIRECRACKER\\kosmos_agent
    python logos_test.py                    # roda todos os casos
    python logos_test.py --caso 1           # roda apenas caso 1
    python logos_test.py --caso 2 --verbose # mostra resposta completa
    python logos_test.py --avaliar          # mostra rubrica de avaliação
"""

import sys
import json
import time
import argparse
import textwrap
from typing import Optional

# ══════════════════════════════════════════════════════════════════════
# OS 3 CASOS DE TESTE — ABSTRACTS COM CONTRADIÇÕES REAIS
# ══════════════════════════════════════════════════════════════════════

CASOS = [

    {
        "id": 1,
        "titulo": "Paradoxo da Gordura Saturada",
        "dominio": "Nutrição / Epidemiologia",
        "dificuldade": "MEDIA",
        "abstracts": [
            {
                "fonte": "Siri-Tarino et al., American Journal of Clinical Nutrition, 2010",
                "texto": (
                    "Meta-análise de 21 estudos prospectivos (n=347.747, seguimento médio 14 anos) "
                    "não encontrou associação significativa entre consumo de gordura saturada e "
                    "incidência de doença coronariana ou AVC. RR=1.07 (IC 95%: 0.96-1.19)."
                )
            },
            {
                "fonte": "Mensink & Katan, New England Journal of Medicine, 1992",
                "texto": (
                    "Ensaio clínico controlado demonstrou que substituição isocalórica de "
                    "carboidratos por gordura saturada eleva LDL-colesterol em 8.4 mg/dL "
                    "e reduz HDL em 1.8 mg/dL, alterando desfavoravelmente o perfil lipídico "
                    "em 28 voluntários saudáveis (p<0.001)."
                )
            },
            {
                "fonte": "Chowdhury et al., Annals of Internal Medicine, 2014",
                "texto": (
                    "Revisão sistemática de 76 estudos observacionais e ensaios randomizados "
                    "concluiu que evidências não suportam diretrizes que recomendam alta ingestão "
                    "de ácidos graxos poli-insaturados e baixa de saturados para redução de "
                    "risco cardiovascular. A associação entre tipo de gordura e desfecho clínico "
                    "foi não-significativa na maioria das análises."
                )
            },
        ],
        "paradoxo_esperado": (
            "Gordura saturada eleva marcadores lipídicos (Mensink) mas não aumenta "
            "eventos cardiovasculares (Siri-Tarino, Chowdhury) — paradoxo biomarcador vs. desfecho."
        ),
        "hipotese_modelo": (
            "O LDL-total é um proxy inadequado de risco cardiovascular quando aumentado "
            "por gordura saturada, pois o subtipo LDL-A (partículas grandes e flutuantes) "
            "difere do LDL-B (pequenas e densas) em aterogenicidade. A hipótese: "
            "gordura saturada eleva preferencialmente LDL-A, neutro em risco, enquanto "
            "carboidratos refinados elevam LDL-B, aterogênico."
        ),
        "experimento_modelo": (
            "Ensaio cruzado: 60 sujeitos, 3 dietas isocalóricas por 8 semanas cada "
            "(alta gordura saturada, alta carbo refinado, mediterrânea). "
            "Medir: LDL por subfração (NMR), não apenas LDL total. Custo: reagentes NMR "
            "já disponíveis em hospitais universitários. Falsificador: se LDL-A não "
            "diferir entre dietas, a hipótese cai."
        ),
    },

    {
        "id": 2,
        "titulo": "Paradoxo do Sono e Memória",
        "dominio": "Neurociência / Psicologia Cognitiva",
        "dificuldade": "ALTA",
        "abstracts": [
            {
                "fonte": "Stickgold et al., Science, 2000",
                "texto": (
                    "Privação de sono nas primeiras 30 horas após aprendizado de tarefa "
                    "motora sequencial eliminou completamente a melhora de desempenho "
                    "observada após sono normal. Sugere que o sono é necessário para "
                    "consolidação de memória procedural (n=24, p<0.001)."
                )
            },
            {
                "fonte": "Shadmehr & Holcomb, Science, 1997",
                "texto": (
                    "Memória para tarefa de adaptação motora mostrou-se estável por até "
                    "5 horas após aprendizado sem necessidade de sono, com consolidação "
                    "ocorrendo durante vigília ativa. Interferência foi reduzida quando "
                    "sujeitos permaneceram acordados mas inativos (n=32)."
                )
            },
            {
                "fonte": "Cai et al., PNAS, 2009",
                "texto": (
                    "Sono REM, mas não sono de ondas lentas (SWS), prediz insight criativo "
                    "em problema de restruturação numérica. Sujeitos acordados por período "
                    "equivalente não mostraram ganho de insight (OR=2.3, IC95%: 1.3-4.1). "
                    "Memória declarativa e procedural podem ter mecanismos de consolidação "
                    "dissociáveis."
                )
            },
        ],
        "paradoxo_esperado": (
            "Sono é necessário (Stickgold) mas vigília ativa também consolida (Shadmehr) — "
            "contradição sobre o papel do sono na consolidação motora vs. tempo pós-aprendizado."
        ),
        "hipotese_modelo": (
            "A consolidação de memória motora ocorre em duas fases dissociáveis: "
            "estabilização (primeiras horas, independe de sono, depende de ausência de "
            "interferência motora) e otimização (requer sono REM, produz melhora além do "
            "baseline). Stickgold mediu otimização; Shadmehr mediu estabilização."
        ),
        "experimento_modelo": (
            "Protocolo 2x2: grupo sono vs. vigília X tarefa motora vs. cognitiva. "
            "4 medições: imediato, 4h, 12h, 24h pós-aprendizado. "
            "Polissonografia para confirmar sono REM. "
            "Falsificador: se melhora de desempenho ocorrer igualmente em vigília "
            "e sono sem diferença na fase REM, a hipótese de dois estágios cai."
        ),
    },

    {
        "id": 3,
        "titulo": "Paradoxo do Antibiótico e Microbioma",
        "dominio": "Microbiologia / Imunologia",
        "dificuldade": "ALTA",
        "abstracts": [
            {
                "fonte": "Blaser & Falkow, Nature Reviews Microbiology, 2009",
                "texto": (
                    "Uso de antibióticos na infância (primeiros 6 anos) correlaciona-se com "
                    "aumento de 84% no risco de doença inflamatória intestinal na vida adulta "
                    "(HR=1.84, IC95%: 1.27-2.66). Hipótese: depleção de microbiota comensal "
                    "compromete treinamento imunológico, aumentando autoimunidade."
                )
            },
            {
                "fonte": "Olszak et al., Science, 2012",
                "texto": (
                    "Camundongos germ-free (sem microbiota) apresentaram hiperreatividade "
                    "imune ao nascer, mas exposição a microbiota normal nas primeiras semanas "
                    "de vida normalizou resposta. Exposição tardia (adulto) foi insuficiente. "
                    "Identificada janela crítica de programação imunológica neonatal."
                )
            },
            {
                "fonte": "Desselberger, PLOS Pathogens, 2018",
                "texto": (
                    "Em populações rurais africanas sem acesso a antibióticos, taxas de "
                    "doenças autoimunes (diabetes tipo 1, esclerose múltipla) são 10-30x "
                    "menores que em países industrializados — mas mortalidade infantil por "
                    "infecção bacteriana é 40x maior. A ausência de antibióticos protege "
                    "o microbioma mas custa vidas. O tradeoff não é linear."
                )
            },
        ],
        "paradoxo_esperado": (
            "Antibióticos destroem microbioma saudável e aumentam autoimunidade (Blaser), "
            "mas sem eles a mortalidade infantil explode (Desselberger) — "
            "paradoxo entre proteção imunológica e sobrevivência imediata."
        ),
        "hipotese_modelo": (
            "A janela crítica de Olszak sugere que o dano não é do antibiótico em si, "
            "mas do timing. Hipótese: antibióticos administrados ANTES dos 6 meses de vida "
            "causam dano imunológico irreversível; após 18 meses, o impacto é mínimo pois "
            "a janela de programação imune está fechada. O protocolo atual não diferencia "
            "por janela ontogenética."
        ),
        "experimento_modelo": (
            "Coorte retrospectiva em 3 países com diferentes políticas de antibiótico "
            "pediátrico. Estratificar por idade de primeira exposição (<6m, 6-18m, >18m). "
            "Desfecho: marcadores imunes aos 10 anos (Th17/Treg ratio, IgE). "
            "Falsificador: se o risco for uniforme independente da janela de exposição, "
            "a hipótese cai e o mecanismo é puramente cumulativo."
        ),
    },

]

# ══════════════════════════════════════════════════════════════════════
# PROMPT DO TESTE — O COMANDO L.O.G.O.S.
# ══════════════════════════════════════════════════════════════════════

def build_prompt(caso: dict) -> str:
    abstracts_text = ""
    for i, ab in enumerate(caso["abstracts"], 1):
        abstracts_text += f"\n[ABSTRACT {i}] {ab['fonte']}\n{ab['texto']}\n"

    return f"""TESTE L.O.G.O.S. — Raciocínio Científico Puro
Domínio: {caso['dominio']} | Dificuldade: {caso['dificuldade']}

Você recebeu 3 abstracts de estudos científicos reais que apresentam resultados aparentemente contraditórios.
{abstracts_text}

MISSÃO (resposta máxima: 300 palavras):

1. CONTRADIÇÃO — Identifique a contradição central entre os estudos. Seja preciso: qual variável, qual magnitude, qual direção do efeito conflita?

2. HIPÓTESE — Formule UMA hipótese parcimoniosa que reconcilie os dados. A hipótese deve:
   - Introduzir uma variável moderadora ou mecanismo oculto
   - Ser mais simples que assumir que algum estudo está errado
   - Ser expressa em forma falsificável: "Se X, então Y deve ser observado"

3. EXPERIMENTO — Proponha um experimento de baixo custo para falsear sua hipótese. Especifique: design, n amostral estimado, medição crítica e o dado que derrubaria sua hipótese.

PROIBIDO: "mais pesquisas são necessárias" sem especificar qual. Concordar com todos os estudos simultaneamente sem resolver a tensão. Respostas genéricas.
"""

# ══════════════════════════════════════════════════════════════════════
# RUBRICA DE AVALIAÇÃO
# ══════════════════════════════════════════════════════════════════════

RUBRICA = """
╔══════════════════════════════════════════════════════════════════╗
║          RUBRICA L.O.G.O.S. — Avaliação de Resposta             ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CRITÉRIO 1 — Precisão da Contradição (0-3 pts)                 ║
║    0: Não identificou contradição real                           ║
║    1: Identificou superficialmente ("estudos divergem")          ║
║    2: Identificou a variável em conflito                         ║
║    3: Identificou variável + magnitude + direção do efeito       ║
║                                                                  ║
║  CRITÉRIO 2 — Qualidade da Hipótese (0-4 pts)                   ║
║    0: Sem hipótese ou hipótese circular                          ║
║    1: Hipótese presente mas não falsificável                     ║
║    2: Hipótese falsificável mas óbvia                            ║
║    3: Hipótese com variável moderadora não-trivial               ║
║    4: Hipótese elegante + predição quantitativa                  ║
║                                                                  ║
║  CRITÉRIO 3 — Design Experimental (0-3 pts)                     ║
║    0: Sem experimento ou experimento impossível                  ║
║    1: Experimento vago ("testar em laboratório")                 ║
║    2: Design claro + medição especificada                        ║
║    3: Design + n amostral + falsificador explícito               ║
║                                                                  ║
║  CRITÉRIO 4 — Anti-Sycophancy (0-2 pts)                         ║
║    0: Concordou com todos os estudos sem resolver tensão         ║
║    1: Tomou posição mas sem justificativa lógica                 ║
║    2: Tomou posição + apontou qual estudo tem limitação          ║
║                                                                  ║
║  CRITÉRIO 5 — Concisão (0-2 pts)                                ║
║    0: Acima de 400 palavras ou abaixo de 100                     ║
║    1: 300-400 palavras                                           ║
║    2: Dentro de 300 palavras com alta densidade                  ║
║                                                                  ║
║  PONTUAÇÃO TOTAL: 14 pts                                        ║
║    12-14: Nível Nobel — raciocínio de fronteira                  ║
║     9-11: Nível PhD — sólido e rigoroso                          ║
║     6-8:  Nível MSc — competente mas conservador                 ║
║     3-5:  Nível graduação — superficial                          ║
║     0-2:  Falha — não respondeu à missão                         ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════

def run_test(caso: dict, verbose: bool = False, use_kosmos: bool = True):
    prompt = build_prompt(caso)
    print(f"\n{'='*65}")
    print(f"TESTE L.O.G.O.S. #{caso['id']} — {caso['titulo']}")
    print(f"Domínio: {caso['dominio']} | Dificuldade: {caso['dificuldade']}")
    print(f"{'='*65}")

    if verbose:
        print("\n[PROMPT ENVIADO]")
        print(prompt)
        print("\n[PARADOXO ESPERADO]")
        print(f"  {caso['paradoxo_esperado']}")

    if use_kosmos:
        try:
            from llm_client import get_llm_client
            llm = get_llm_client()

            system = (
                "Você é um cientista de fronteira com raciocínio hipotético-dedutivo rigoroso. "
                "Nunca concorda com premissas contraditórias sem resolver a tensão. "
                "Sempre formula hipóteses falsificáveis e experimentos específicos. "
                "Proibido: conclusões vagas, 'mais pesquisas são necessárias' sem especificar qual."
            )

            print(f"\n[ENVIANDO PARA DEEPSEEK...]\n")
            t0 = time.time()

            response = llm.chat(
                user_message=prompt,
                system_prompt=system,
                max_tokens=600,
                temperature=0.7,
            )

            elapsed = time.time() - t0
            words = len(response.split())

            print(f"[RESPOSTA — {words} palavras | {elapsed:.1f}s]\n")
            print(response)
            print(f"\n{'─'*65}")
            print(f"[GABARITO — Hipótese modelo]")
            print(textwrap.fill(caso['hipotese_modelo'], width=65))
            print(f"\n[GABARITO — Experimento modelo]")
            print(textwrap.fill(caso['experimento_modelo'], width=65))
            print(f"{'─'*65}")

            return {"caso": caso['id'], "resposta": response, "tempo": elapsed, "palavras": words}

        except ImportError:
            print("[AVISO] llm_client não encontrado. Rodando em modo demo.")
            use_kosmos = False

    if not use_kosmos:
        print("\n[MODO DEMO — sem LLM]")
        print("Prompt que seria enviado:")
        print(textwrap.indent(prompt, "  "))
        print(f"\n[GABARITO — Hipótese modelo]")
        print(textwrap.fill(caso['hipotese_modelo'], width=65))
        print(f"\n[GABARITO — Experimento modelo]")
        print(textwrap.fill(caso['experimento_modelo'], width=65))
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Projeto L.O.G.O.S. — Teste de Popper-Turing para o KOSMOS"
    )
    parser.add_argument("--caso",    type=int, choices=[1,2,3], help="Roda apenas o caso N")
    parser.add_argument("--verbose", action="store_true",       help="Mostra prompt completo")
    parser.add_argument("--demo",    action="store_true",       help="Roda sem LLM (modo demo)")
    parser.add_argument("--avaliar", action="store_true",       help="Mostra rubrica de avaliação")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║          PROJETO L.O.G.O.S. — KOSMOS Agent              ║")
    print("║   Logical Observation & Generative Output Synthesis     ║")
    print("║   Teste de Popper-Turing Lógico                         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    if args.avaliar:
        print(RUBRICA)
        return

    casos_para_rodar = [c for c in CASOS if not args.caso or c["id"] == args.caso]
    use_kosmos = not args.demo

    resultados = []
    for caso in casos_para_rodar:
        r = run_test(caso, verbose=args.verbose, use_kosmos=use_kosmos)
        if r:
            resultados.append(r)
        if len(casos_para_rodar) > 1:
            time.sleep(2)

    if resultados:
        print(f"\n{'='*65}")
        print(f"SUMÁRIO — {len(resultados)} testes executados")
        for r in resultados:
            print(f"  Caso #{r['caso']}: {r['palavras']} palavras | {r['tempo']:.1f}s")
        print(f"{'='*65}")
        print(RUBRICA)


if __name__ == "__main__":
    main()
