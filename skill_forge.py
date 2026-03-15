"""
skill_forge.py — KOSMOS Agent v2.3
=====================================
O Motor Cognitivo de Transmutação de Skills.

Enquanto o SkillRouter SELECIONA skills existentes,
o SkillForge CRIA e TRANSMUTA skills em tempo de execução.

Arquitetura (baseada no protocolo Kosmos Supreme):

    Skill Base        →  SkillForge.transmute()  →  Skill Novo
    (FRONTEND_DESIGN)    [6 Pilares Cognitivos]     (SCIENTIFIC_ACCEL)

    Problema Novo     →  SkillForge.forge()      →  Skill Sintético
    (sem match)          [Fusão de Assinaturas]      (salvo em registry)

Fusão de Assinaturas (os 3 modelos cognitivos):
    DIVERGÊNCIA CRIATIVA    — mapeamento cruzado de domínios
    RIGOR FORMAL            — formulação matemática/lógica obrigatória
    ESTRUTURA METODOLÓGICA  — transparência, falsificabilidade, vieses

Os 6 Pilares de Análise:
    1. Cientista Cognitivo      — primeiros princípios, anti-analogia clichê
    2. Especialista IHC/UX      — estrutura do output para consumo humano
    3. Engenheiro de Cognição   — ancoragem nas leis fundamentais
    4. Psicólogo Cognitivo      — eliminação do viés de confirmação
    5. Neurocientista Comput.   — cruzamento estocástico de variáveis
    6. Pesquisador IA           — extração de dark knowledge do espaço latente

Lógica de Transmutação (Logic Patch):
    estética visual      →  elegância matemática
    impacto emocional    →  tensão epistêmica / falsificabilidade
    anti-banalidade      →  anti-consenso seguro (universal a todos domínios)
    tom extremo          →  ângulo investigativo ousado
    compromisso estético →  compromisso epistêmico
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

logger = logging.getLogger("kosmos.skill_forge")


# ══════════════════════════════════════════════════════════════════════
# ESTRUTURA DE UM SKILL FORJADO
# ══════════════════════════════════════════════════════════════════════

@dataclass
class ForgedSkill:
    """Um skill criado ou transmutado pelo SkillForge."""
    name: str
    domain: str
    description: str
    keywords: list
    excludes: list
    priority: int
    protocol: str
    origin: str           # "static" | "transmuted" | "forged"
    source_skill: str     # nome do skill base (se transmutado)
    pillars_used: list    # quais dos 6 pilares foram aplicados
    signature_blend: dict # pesos das 3 assinaturas cognitivas

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)

    def id(self) -> str:
        return hashlib.md5(self.name.encode()).hexdigest()[:8]


# ══════════════════════════════════════════════════════════════════════
# TEMPLATES DE TRANSMUTAÇÃO — O "LOGIC PATCH"
# ══════════════════════════════════════════════════════════════════════

# Cada domínio-alvo define:
#   base_swap: como os conceitos da skill-base são reinterpretados
#   phase1_label: nome da fase de reflexão
#   phase1_pillars: quais pilares ativar
#   anti_banality: o que evitar (equivalente ao "AI Slop" do frontend)
#   commitment_label: como se chama o "compromisso" neste domínio

TRANSMUTATION_TEMPLATES = {

    "SCIENTIFIC_ACCELERATION": {
        "description": "Geração de hipóteses de fronteira, síntese epistêmica, design experimental",
        "keywords": [
            "hipotese", "hipótese", "teoria", "experimento", "ciência", "ciencia",
            "pesquisa", "research", "descoberta", "fenomeno", "fenômeno",
            "anomalia", "modelo cientifico", "modelo científico", "simulacao",
            "equacao", "equação", "formulacao", "formulação", "tese",
            "interdisciplinar", "paradigma", "falsificavel", "falsificável",
            "mecanismo biologico", "mecanismo biológico", "fisica", "física",
            "biologia", "quimica", "química", "neurociencia", "neurociência",
        ],
        "excludes": ["landing", "html", "css", "slide", "apresentacao", "email"],
        "priority": 12,
        "base_swap": {
            "estética visual":       "elegância matemática",
            "impacto emocional":     "tensão epistêmica e falsificabilidade",
            "tom extremo":           "ângulo investigativo ousado e contra-intuitivo",
            "compromisso estético":  "compromisso epistêmico (a hipótese-núcleo)",
            "anti-AI slop":         "anti-consenso seguro; jamais 'mais pesquisas são necessárias' sem propor qual",
            "composição espacial":   "estrutura lógica: Axiomas → Anomalia → Hipótese → Mecanismo → Falsificação",
        },
        "phase1_label": "RACIOCÍNIO EPISTÊMICO",
        "phase1_content": (
            "  PARADIGMA DESAFIADO: Qual consenso atual esta análise questiona?\n"
            "  ÂNGULO INVESTIGATIVO: Escolha uma lente:\n"
            "    Reducionismo Matemático | Holismo de Sistemas Complexos |\n"
            "    Biomimética | Mecânica Estatística | Física Computacional |\n"
            "    Teoria da Informação | Dinâmica de Redes\n"
            "    PROIBIDO: revisão de literatura genérica.\n\n"
            "  VARIÁVEL OCULTA: O que os pesquisadores tradicionais estão ignorando?\n"
            "  FORMULAÇÃO FORMAL: Expresse a hipótese em notação matemática ou\n"
            "    lógica de primeira ordem antes de qualquer texto.\n"
            "  FALSIFICABILIDADE: Qual experimento poderia provar que você está errado?\n"
            "  DARK KNOWLEDGE: Qual inferência implícita (não publicada explicitamente)\n"
            "    emerge do cruzamento de domínios distantes?\n"
            "  COMPROMISSO EPISTÊMICO: Uma frase que resume a hipótese-núcleo.\n"
        ),
        "phase2_label": "SÍNTESE CIENTÍFICA",
        "phase2_content": (
            "  Estrutura obrigatória do output:\n"
            "    1. AXIOMAS — premissas aceitas como base\n"
            "    2. ANOMALIA — o fenômeno que o paradigma atual não explica\n"
            "    3. HIPÓTESE — formulação formal (equação, lógica ou pseudo-código)\n"
            "    4. MECANISMO — como o processo ocorre passo a passo\n"
            "    5. PREDIÇÕES — o que deve ser observado se a hipótese for verdadeira\n"
            "    6. DESIGN EXPERIMENTAL — protocolo mínimo para falsificação\n"
            "    7. PONTOS CEGOS — como esta teoria pode estar completamente errada\n"
        ),
        "anti_banality": (
            "  Revisões de literatura sem hipótese nova\n"
            "  Conclusões do tipo 'mais pesquisas são necessárias' sem especificar qual\n"
            "  Hipóteses lineares que confirmam o paradigma dominante\n"
            "  Analogias clichês sem formulação matemática\n"
            "  Linguagem vaga: 'sinergia', 'paradigma shift', 'holístico'\n"
        ),
        "pillars": [
            ("Cientista Cognitivo",     "Primeiros princípios. Proibir analogias clichês."),
            ("Engenheiro de Cognição",  "Ancoragem nas leis fundamentais. Nenhuma teoria viola termodinâmica sem prova."),
            ("Psicólogo Cognitivo",     "Advogado do Diabo Epistêmico. Eliminar viés de confirmação."),
            ("Neurocientista Comput.",  "Cruzar variáveis não correlacionadas. Simular 'momentos Eureka'."),
            ("Pesquisador IA",          "Extrair dark knowledge do espaço latente interdisciplinar."),
        ],
        "signature_blend": {"divergencia_criativa": 0.4, "rigor_formal": 0.4, "estrutura_metodologica": 0.2},
    },

    "STRATEGIC_INTELLIGENCE": {
        "description": "Análise estratégica, inteligência competitiva, cenários futuros",
        "keywords": [
            "estrategia", "estratégia", "competidor", "mercado", "tendencia",
            "cenario", "cenário", "swot", "porter", "vantagem competitiva",
            "posicionamento", "disrupcao", "disrupção", "oportunidade",
            "ameaca", "ameaça", "inteligencia", "inteligência de mercado",
            "expansao", "expansão", "fusao", "fusão", "aquisicao", "aquisição",
        ],
        "excludes": ["html", "css", "codigo", "script"],
        "priority": 11,
        "base_swap": {
            "estética visual":       "clareza estratégica e impacto decisório",
            "impacto emocional":     "tensão competitiva e urgência situacional",
            "tom extremo":           "perspectiva estratégica contrarian",
            "compromisso estético":  "tese estratégica central",
            "anti-AI slop":         "anti-análise genérica; jamais SWOT sem insights acionáveis",
        },
        "phase1_label": "INTELIGÊNCIA SITUACIONAL",
        "phase1_content": (
            "  CAMPO DE FORÇAS: Quais as 3 forças que mais moldam este mercado agora?\n"
            "  PERSPECTIVA CONTRARIAN: O que todos os players estão ignorando?\n"
            "  ASSIMETRIA: Onde está o desequilíbrio informacional aproveitável?\n"
            "  HORIZONTE TEMPORAL: 90 dias | 1 ano | 5 anos — qual escala importa aqui?\n"
            "  TESE ESTRATÉGICA: Uma frase que captura a aposta central.\n"
        ),
        "phase2_label": "SÍNTESE ESTRATÉGICA",
        "phase2_content": (
            "  Estrutura obrigatória:\n"
            "    1. CONTEXTO — o que mudou recentemente que torna este momento único\n"
            "    2. MAPA DE FORÇAS — atores, vetores e intensidades\n"
            "    3. ASSIMETRIAS — vantagens não exploradas\n"
            "    4. CENÁRIOS — 3 futuros possíveis com probabilidade e trigger\n"
            "    5. OPÇÕES ESTRATÉGICAS — movimentos específicos, não genéricos\n"
            "    6. RISCOS OCULTOS — o que pode invalidar tudo isso\n"
        ),
        "anti_banality": (
            "  SWOT genérico sem dados específicos\n"
            "  'O mercado está crescendo' sem taxa, contexto e implicação\n"
            "  Recomendações tipo 'inovar continuamente'\n"
            "  Análise que confirma o que o cliente já sabe\n"
        ),
        "pillars": [
            ("Cientista Cognitivo",   "Mapear o sistema antes de propor ação."),
            ("Psicólogo Cognitivo",   "Identificar onde o viés do cliente distorce a análise."),
            ("Pesquisador IA",        "Extrair sinais fracos não óbvios do contexto."),
        ],
        "signature_blend": {"divergencia_criativa": 0.3, "rigor_formal": 0.3, "estrutura_metodologica": 0.4},
    },

    "PHILOSOPHICAL_REASONING": {
        "description": "Análise filosófica, ética aplicada, epistemologia, lógica formal",
        "keywords": [
            "filosofia", "etica", "ética", "epistemologia", "ontologia",
            "metafisica", "metafísica", "logica", "lógica", "argumento",
            "premissa", "conclusao", "conclusão", "contradicao", "contradição",
            "paradoxo", "dilema", "moral", "consciencia", "consciência",
            "livre arbitrio", "livre-arbítrio", "determinismo", "existencia",
            "existência", "verdade", "conhecimento", "justificacao",
        ],
        "excludes": ["html", "css", "codigo", "script", "planilha"],
        "priority": 10,
        "base_swap": {
            "estética visual":       "coerência lógica e densidade conceitual",
            "impacto emocional":     "tensão dialética e poder de questionamento",
            "tom extremo":           "posição filosófica radical porém defensável",
            "compromisso estético":  "tese filosófica central",
            "anti-AI slop":         "anti-ecumenismo filosófico; tomar posição e defendê-la",
        },
        "phase1_label": "POSICIONAMENTO FILOSÓFICO",
        "phase1_content": (
            "  TRADIÇÃO ESCOLHIDA: Analítica | Continental | Pragmatista |\n"
            "    Fenomenológica | Estoica | Budista | Outra — e por quê esta?\n"
            "  TESE CENTRAL: Uma proposição clara que pode ser verdadeira ou falsa.\n"
            "  OBJEÇÃO PRINCIPAL: O argumento mais forte contra sua tese.\n"
            "  MÉTODO: Dedução | Indução | Abdução | Dialética | Desconstrução?\n"
            "  COMPROMISSO: Uma frase que define a posição filosófica defendida.\n"
        ),
        "phase2_label": "ARGUMENTAÇÃO FORMAL",
        "phase2_content": (
            "  Estrutura obrigatória:\n"
            "    1. DEFINIÇÕES — termos centrais definidos com precisão\n"
            "    2. PREMISSAS — listadas numeradas, cada uma defensável\n"
            "    3. ARGUMENTO — a inferência explícita (P1 + P2 → C)\n"
            "    4. OBJEÇÕES — as 2-3 mais sérias com respostas\n"
            "    5. IMPLICAÇÕES — o que muda no mundo se a tese for verdadeira\n"
            "    6. LIMITES — onde o argumento não se aplica\n"
        ),
        "anti_banality": (
            "  'É complexo e depende do ponto de vista'\n"
            "  Apresentar todos os lados sem tomar posição\n"
            "  Citar filósofos sem construir argumento próprio\n"
            "  Confundir ética descritiva com normativa\n"
        ),
        "pillars": [
            ("Cientista Cognitivo",  "Primeiros princípios. Sem pressupostos não declarados."),
            ("Psicólogo Cognitivo",  "Identificar e nomear os vieses do argumento."),
            ("Engenheiro de Cognição", "Verificar consistência lógica formal."),
        ],
        "signature_blend": {"divergencia_criativa": 0.2, "rigor_formal": 0.5, "estrutura_metodologica": 0.3},
    },
}


# ══════════════════════════════════════════════════════════════════════
# O MOTOR DE TRANSMUTAÇÃO
# ══════════════════════════════════════════════════════════════════════

class SkillForge:
    """
    Motor cognitivo que cria e transmuta skills em tempo de execução.

    Dois modos de operação:

    1. TRANSMUTE — pega um skill existente e reescreve seus princípios
       para um novo domínio usando o Logic Patch:
           forge.transmute("FRONTEND_DESIGN", "SCIENTIFIC_ACCELERATION")

    2. FORGE — cria um skill novo a partir de um domínio ainda não mapeado,
       usando os 6 pilares cognitivos e a fusão de assinaturas:
           forge.forge("Análise Jurídica de Contratos")

    O resultado em ambos os casos é um ForgedSkill pronto para ser
    injetado no system prompt via SkillRouter.add_skill().
    """

    def __init__(self, registry_path: str = "skills_registry.json"):
        self.registry_path = Path(registry_path)
        self.registry: dict = {}          # name → ForgedSkill
        self.templates = TRANSMUTATION_TEMPLATES
        self._load_registry()

    # ── Persistência ──────────────────────────────────────────────────

    def _load_registry(self):
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self.registry = {k: ForgedSkill.from_dict(v) for k, v in raw.items()}
                logger.info(f"SkillForge: {len(self.registry)} skills carregados do registry")
            except Exception as e:
                logger.warning(f"SkillForge: erro ao carregar registry ({e}), iniciando vazio")

    def _save_registry(self):
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(
                    {k: v.to_dict() for k, v in self.registry.items()},
                    f, ensure_ascii=False, indent=2
                )
        except Exception as e:
            logger.warning(f"SkillForge: erro ao salvar registry ({e})")

    # ── Transmutação ──────────────────────────────────────────────────

    def transmute(self, source_skill_name: str, target_domain: str,
                  source_skill=None) -> ForgedSkill:
        """
        Transmuta um skill existente para um novo domínio.

        Args:
            source_skill_name: nome do skill base (ex: "FRONTEND_DESIGN")
            target_domain: domínio-alvo do template (ex: "SCIENTIFIC_ACCELERATION")
            source_skill: objeto Skill (opcional; se None usa o nome apenas para referência)

        Returns:
            ForgedSkill pronto para uso
        """
        if target_domain not in self.templates:
            raise ValueError(
                f"Template '{target_domain}' não existe. "
                f"Disponíveis: {list(self.templates.keys())}"
            )

        template = self.templates[target_domain]
        skill_id = f"{source_skill_name}_→_{target_domain}"

        if skill_id in self.registry:
            logger.info(f"SkillForge: cache hit para '{skill_id}'")
            return self.registry[skill_id]

        logger.info(f"SkillForge: transmutando '{source_skill_name}' → '{target_domain}'")

        protocol = self._build_protocol(template, source_skill_name)

        forged = ForgedSkill(
            name=f"{target_domain}",
            domain=target_domain,
            description=template["description"],
            keywords=template["keywords"],
            excludes=template["excludes"],
            priority=template["priority"],
            protocol=protocol,
            origin="transmuted",
            source_skill=source_skill_name,
            pillars_used=[p[0] for p in template.get("pillars", [])],
            signature_blend=template.get("signature_blend", {}),
        )

        self.registry[skill_id] = forged
        self._save_registry()
        return forged

    def forge(self, task_description: str, domain_hint: str = "") -> Optional[ForgedSkill]:
        """
        Forja um skill novo para um domínio ainda não coberto,
        usando os 6 pilares cognitivos e a fusão de assinaturas.

        Para domínios não mapeados em TRANSMUTATION_TEMPLATES,
        este método tenta inferir a estrutura a partir da descrição.

        Args:
            task_description: descrição do domínio ou tarefa
            domain_hint: nome sugerido para o skill (opcional)

        Returns:
            ForgedSkill ou None se não conseguir inferir
        """
        # Tenta match por keywords nos templates existentes
        task_lower = task_description.lower()
        best_template = None
        best_score = 0

        for domain, template in self.templates.items():
            hits = sum(1 for kw in template["keywords"] if kw in task_lower)
            if hits > best_score:
                best_score = hits
                best_template = domain

        if best_template and best_score >= 2:
            logger.info(f"SkillForge: forge → match com template '{best_template}' (score={best_score})")
            return self.transmute("AUTO_DETECTED", best_template)

        # Domínio completamente novo — inferência por pilares
        logger.info(f"SkillForge: forge → domínio novo, inferindo pelos pilares")
        return self._forge_from_pillars(task_description, domain_hint)

    def _forge_from_pillars(self, description: str, name: str = "") -> ForgedSkill:
        """
        Cria um skill genérico usando os 6 pilares cognitivos universais.
        Fallback para domínios completamente novos.
        """
        skill_name = name.upper().replace(" ", "_") if name else "CUSTOM_DOMAIN"

        protocol = (
            "\n\n[SKILL FORJADO: " + skill_name + "]\n"
            "Domínio: " + description + "\n\n"
            "Aplicando os 6 Pilares Cognitivos Universais:\n\n"
            "FASE 1 — [ANÁLISE MULTIDIMENSIONAL]:\n\n"
            "  PILAR 1 — Primeiros Princípios:\n"
            "    Qual é o problema fundamental, despido de pressupostos?\n"
            "    Proibido usar analogias sem antes reconstruir do zero.\n\n"
            "  PILAR 2 — Estrutura do Output:\n"
            "    Como o resultado deve ser organizado para consumo máximo?\n"
            "    Modular, escaneável, com hierarquia de importância clara.\n\n"
            "  PILAR 3 — Ancoragem em Leis Fundamentais:\n"
            "    Quais as restrições invioláveis deste domínio?\n"
            "    Nenhuma proposta viola essas restrições sem justificativa explícita.\n\n"
            "  PILAR 4 — Advogado do Diabo:\n"
            "    Qual o argumento mais forte contra a abordagem escolhida?\n"
            "    Nomear e responder antes de prosseguir.\n\n"
            "  PILAR 5 — Cruzamento Estocástico:\n"
            "    Qual domínio DISTANTE pode iluminar este problema?\n"
            "    Forçar pelo menos 1 conexão interdisciplinar não óbvia.\n\n"
            "  PILAR 6 — Dark Knowledge:\n"
            "    O que é implícito mas não dito no contexto deste problema?\n"
            "    Articular o não-dito antes de responder o dito.\n\n"
            "FASE 2 — [EXECUÇÃO]:\n"
            "  Resposta que integra os 6 pilares.\n"
            "  Anti-banalidade: evitar o consenso seguro em qualquer forma.\n"
            "  Compromisso: uma frase que resume a tese central.\n"
        )

        forged = ForgedSkill(
            name=skill_name,
            domain="CUSTOM",
            description=description,
            keywords=[w for w in description.lower().split() if len(w) > 4][:10],
            excludes=[],
            priority=9,
            protocol=protocol,
            origin="forged",
            source_skill="PILLARS",
            pillars_used=["Cientista Cognitivo", "IHC/UX", "Engenheiro de Cognição",
                          "Psicólogo Cognitivo", "Neurocientista Comput.", "Pesquisador IA"],
            signature_blend={"divergencia_criativa": 0.33,
                             "rigor_formal": 0.33,
                             "estrutura_metodologica": 0.34},
        )

        self.registry[skill_name] = forged
        self._save_registry()
        return forged

    def _build_protocol(self, template: dict, source_name: str) -> str:
        """Constrói o protocolo completo de um skill a partir do template."""
        domain = template.get("phase1_label", "ANÁLISE")
        phase2 = template.get("phase2_label", "EXECUÇÃO")

        lines = []
        lines.append(f"\n\n[SKILL ATIVO: {template.get('phase1_label', 'CUSTOM')}]")
        lines.append(f"Transmutado de: {source_name}")
        lines.append(f"Domínio: {template['description']}\n")

        # Assinatura cognitiva
        blend = template.get("signature_blend", {})
        if blend:
            blend_str = " | ".join(f"{k.replace('_',' ').title()} {int(v*100)}%" for k, v in blend.items())
            lines.append(f"Assinatura: [{blend_str}]\n")

        # Pilares ativos
        pillars = template.get("pillars", [])
        if pillars:
            lines.append("Pilares Cognitivos Ativos:")
            for name, desc in pillars:
                lines.append(f"  [{name}]: {desc}")
            lines.append("")

        # Fase 1
        lines.append(f"FASE 1 — [{domain}] (OBRIGATÓRIO ANTES DA RESPOSTA):")
        lines.append(template.get("phase1_content", "  Analisar o problema em profundidade.\n"))

        # Fase 2
        lines.append(f"FASE 2 — [{phase2}]:")
        lines.append(template.get("phase2_content", "  Resposta que reflete a Fase 1.\n"))

        # Anti-banalidade
        anti = template.get("anti_banality", "")
        if anti:
            lines.append("PADRÕES PROIBIDOS (anti-consenso genérico):")
            lines.append(anti)

        # Logic Patch — mapeamento de conceitos
        swap = template.get("base_swap", {})
        if swap:
            lines.append("LOGIC PATCH (transmutação de conceitos):")
            for original, transmuted in swap.items():
                lines.append(f"  {original:<25} →  {transmuted}")

        return "\n".join(lines)

    # ── Utilitários ───────────────────────────────────────────────────

    def list_templates(self) -> list:
        """Lista templates de transmutação disponíveis."""
        return [(k, v["description"]) for k, v in self.templates.items()]

    def list_forged(self) -> list:
        """Lista skills já forjados/transmutados no registry."""
        return [(k, v.origin, v.description) for k, v in self.registry.items()]

    def get(self, name: str) -> Optional[ForgedSkill]:
        """Recupera um skill forjado pelo nome."""
        return self.registry.get(name)

    def add_template(self, domain: str, template: dict):
        """Adiciona um template de transmutação customizado."""
        required = ["description", "keywords", "excludes", "priority",
                    "phase1_label", "phase1_content", "phase2_label",
                    "phase2_content", "anti_banality"]
        missing = [k for k in required if k not in template]
        if missing:
            raise ValueError(f"Template incompleto. Faltam: {missing}")
        self.templates[domain] = template
        logger.info(f"SkillForge: template '{domain}' adicionado")


# ══════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM SKILLROUTER + KOSMOS ENGINE
# ══════════════════════════════════════════════════════════════════════
#
# O SkillForge e o SkillRouter trabalham juntos:
#
#   from skill_router import SkillRouter
#   from skill_forge import SkillForge
#   from dataclasses import dataclass
#
#   router = SkillRouter()
#   forge  = SkillForge()
#
#   def get_protocol(task: str) -> str:
#       # 1. Tenta o router (skills estáticos)
#       protocol = router.route(task)
#       if protocol:
#           return protocol
#
#       # 2. Tenta forjar um skill dinâmico
#       forged = forge.forge(task)
#       if forged:
#           return forged.protocol
#
#       # 3. Sem match: base prompt apenas
#       return ""
#
#   # No KosmosEngine:
#   messages = [
#       {'role': 'system', 'content': BASE_PROMPT + get_protocol(task)},
#       {'role': 'user',   'content': task},
#   ]
#
# Para adicionar os skills forjados ao router (opcional):
#   from skill_router import Skill
#   forged = forge.transmute("FRONTEND_DESIGN", "SCIENTIFIC_ACCELERATION")
#   router.add_skill(Skill(
#       name=forged.name, description=forged.description,
#       keywords=forged.keywords, excludes=forged.excludes,
#       priority=forged.priority, protocol=forged.protocol,
#   ))


# ══════════════════════════════════════════════════════════════════════
# EXECUÇÃO DIRETA — DEMONSTRAÇÃO
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    forge = SkillForge(registry_path="/tmp/kosmos_skills_test.json")

    print("\n" + "=" * 65)
    print("KOSMOS SkillForge — Demonstração de Transmutação")
    print("=" * 65)

    # ── Templates disponíveis
    print("\nTemplates de Transmutação Disponíveis:")
    for name, desc in forge.list_templates():
        print(f"  [{name}]")
        print(f"    {desc}")

    # ── Transmutação 1: Frontend → Científico
    print("\n" + "-" * 65)
    print("TRANSMUTAÇÃO: FRONTEND_DESIGN → SCIENTIFIC_ACCELERATION")
    print("-" * 65)
    sci = forge.transmute("FRONTEND_DESIGN", "SCIENTIFIC_ACCELERATION")
    print(f"Skill forjado: {sci.name}")
    print(f"Origem: {sci.origin} (a partir de: {sci.source_skill})")
    print(f"Pilares: {', '.join(sci.pillars_used)}")
    blend_str = " | ".join(f"{k}: {int(v*100)}%" for k, v in sci.signature_blend.items())
    print(f"Assinatura: {blend_str}")
    print(f"\nProtocolo (primeiros 800 chars):")
    print(sci.protocol[:800] + "...")

    # ── Transmutação 2: Software → Estratégico
    print("\n" + "-" * 65)
    print("TRANSMUTAÇÃO: SOFTWARE_ENGINEER → STRATEGIC_INTELLIGENCE")
    print("-" * 65)
    strat = forge.transmute("SOFTWARE_ENGINEER", "STRATEGIC_INTELLIGENCE")
    print(f"Skill forjado: {strat.name}")
    print(f"Pilares: {', '.join(strat.pillars_used)}")

    # ── Forja de domínio novo
    print("\n" + "-" * 65)
    print("FORGE: Domínio novo — 'Análise Jurídica de Contratos'")
    print("-" * 65)
    legal = forge.forge("Análise jurídica de contratos, cláusulas, riscos legais", "LEGAL_ANALYSIS")
    if legal:
        print(f"Skill forjado: {legal.name}")
        print(f"Origem: {legal.origin}")
        print(f"Keywords inferidas: {legal.keywords[:5]}")

    # ── Detecção automática
    print("\n" + "-" * 65)
    print("FORGE AUTO-DETECT: Tarefa de ciência")
    print("-" * 65)
    auto = forge.forge("Quero formular uma hipótese sobre dobramento de proteínas")
    if auto:
        print(f"Template detectado: {auto.name}")
        print(f"Pilares: {', '.join(auto.pillars_used[:3])}...")

    # ── Registry
    print("\n" + "=" * 65)
    print("Skills no Registry:")
    for skill_id, origin, desc in forge.list_forged():
        print(f"  [{origin:12}] {skill_id:<35} — {desc[:45]}")

    print("\n" + "=" * 65)
    print("SkillForge operacional. Registry salvo em /tmp/kosmos_skills_test.json")
    print("=" * 65 + "\n")
