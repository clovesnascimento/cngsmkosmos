"""
skill_router.py — KOSMOS Agent v2.2
=====================================
O Sistema Nervoso Cognitivo do KOSMOS.

Em vez de injetar um único protocolo em todas as tarefas, o SkillRouter
analisa a INTENÇÃO da tarefa e seleciona dinamicamente o skill correto —
exatamente como um sistema nervoso roteia sinais para o órgão adequado.

Arquitetura:
    Tarefa  →  Classifier  →  SkillRouter  →  Protocolo injetado no Proposer
                                    ↓
                            [sem match] → BASE_PROMPT apenas (sem overhead)

Skills disponíveis (mapeados da biblioteca de 16 skills):
    FRONTEND_DESIGN     landing pages, UI, dashboards, componentes web
    SOFTWARE_ENGINEER   código Python/JS, algoritmos, debugging, refatoração
    DOCUMENT_WRITER     relatórios, contratos, documentação técnica (docx)
    DATA_ANALYST        planilhas, análise, visualizações, Excel (xlsx)
    PRESENTER           slides, pitch decks, apresentações (pptx)
    PDF_HANDLER         manipulação, extração, formulários PDF
    MCP_BUILDER         servidores MCP, tools, integrações
    BRAND_IDENTITY      identidade visual, guias de marca, logos
    CREATIVE_ART        arte generativa, canvas, visualizações matemáticas
    COMMUNICATOR        comunicações internas, memos, newsletters

Uso no KosmosEngine (agents.py / planner_tot.py):
    from skill_router import SkillRouter

    router = SkillRouter()
    protocol = router.route(task_description)
    system_prompt = BASE_PROPOSER_PROMPT + protocol
"""

import re
import os
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("kosmos.skill_router")


# ══════════════════════════════════════════════════════════════════════
# DEFINIÇÃO DOS SKILLS
# ══════════════════════════════════════════════════════════════════════

@dataclass
class Skill:
    name: str
    description: str
    keywords: list
    excludes: list
    protocol: str
    priority: int = 0      # maior = mais específico, ganha em empate


# ── SKILL: FRONTEND DESIGN ────────────────────────────────────────────
SKILL_FRONTEND = Skill(
    name="FRONTEND_DESIGN",
    description="Interfaces web, landing pages, dashboards, componentes UI",
    keywords=[
        "landing", "landing page", "pagina", "website", "site institucional",
        "dashboard", "interface", "componente", "component", "html", "css",
        "design", "layout", "frontend", "front-end", "portfolio",
        "loja", "ecommerce", "blog", "visual", "animacao", "ui ", "ux ",
        "home page", "single page", "spa ", "react component",
    ],
    excludes=[
        "scraper", "crawler", "backend", "servidor", "server",
        "websocket", "api endpoint", "web scraping", "deploy",
        "docker", "microvm", "banco de dados",
    ],
    priority=10,
    protocol=(
        "\n\n[SKILL ATIVO: FRONTEND_DESIGN]\n"
        "Você é um Designer Front-End de Elite. Para esta tarefa, siga OBRIGATORIAMENTE:\n\n"
        "FASE 1 — [RACIOCÍNIO ESTÉTICO] (antes de qualquer código):\n"
        "  PROPÓSITO: Para quem? Que problema resolve?\n"
        "  TOM EXTREMO: Uma direção radical — proibido estética genérica.\n"
        "    Opções: Dark-tech | Brutalista | Minimalista cirúrgico |\n"
        "    Maximalista | Retro-futurista | Editorial | Biopunk | Art deco\n"
        "  PALETA: 3-5 cores com variáveis CSS. Dominante + acento cortante.\n"
        "  TIPOGRAFIA: Display + Body com caráter. Proibido Arial/Inter/Roboto.\n"
        "  MOVIMENTO: 1-3 animações de alto impacto (CSS-only ou Canvas).\n"
        "  INESQUECÍVEL: O que alguém vai lembrar em 24h?\n"
        "  COMPROMISSO: Uma frase que resume a alma do design.\n\n"
        "FASE 2 — [EXECUÇÃO]: Código que reflete EXATAMENTE a Fase 1.\n\n"
        "REGRAS TÉCNICAS ABSOLUTAS:\n"
        "  - PROIBIDO triple-quoted strings com HTML/CSS/JS\n"
        "  - OBRIGATÓRIO f.write() linha a linha OU base64\n"
        "  - OBRIGATÓRIO salvar em index.html (o Docker já está em /workspace)\n"
        "  - OBRIGATÓRIO print() de confirmação ao final\n"
        "  - CSS + JS inline no mesmo arquivo HTML\n"
        "  - Google Fonts via link no <head>\n\n"
        "PADRÕES PROIBIDOS (AI Slop):\n"
        "  Gradiente roxo/azul | Cards border-radius:12px empilhados |\n"
        "  Hero texto genérico | Grid 3 ícones idênticos | Azul corporativo\n"
    ),
)

# ── SKILL: SOFTWARE ENGINEER ─────────────────────────────────────────
SKILL_SOFTWARE = Skill(
    name="SOFTWARE_ENGINEER",
    description="Código Python/JS, algoritmos, debugging, refatoração, scripts",
    keywords=[
        "codigo", "código", "script", "função", "function", "classe", "class",
        "algoritmo", "refatorar", "refactor", "debugar", "debug", "corrigir bug",
        "fix bug", "otimizar", "optimize", "implementar", "implement",
        "api ", "endpoint", "backend", "servidor", "server", "microservico",
        "teste", "test", "unittest", "pytest", "docker", "deploy",
        "pipeline", "automacao", "automação", "parser", "scraper",
        "banco de dados", "database", "sql", "query", "migration",
        "websocket", "async", "thread", "process", "subprocess",
        "biblioteca", "library", "package", "module", "import",
        "erro ", "error ", "exception", "traceback", "stack trace",
    ],
    excludes=[
        "landing", "design", "dashboard visual", "portfolio",
        "apresentacao", "slide", "powerpoint",
    ],
    priority=8,
    protocol=(
        "\n\n[SKILL ATIVO: SOFTWARE_ENGINEER]\n"
        "Você é um Engenheiro de Software Sênior. Para esta tarefa:\n\n"
        "FASE 1 — [ANÁLISE TÉCNICA]:\n"
        "  PROBLEMA: Qual é o problema exato? Qual a causa raiz?\n"
        "  ABORDAGEM: Qual padrão/algoritmo resolve com menor complexidade?\n"
        "  RISCOS: Quais edge cases, erros de tipo ou condições de corrida?\n"
        "  DEPENDÊNCIAS: O que o código precisa importar/ter disponível?\n\n"
        "FASE 2 — [IMPLEMENTAÇÃO]:\n"
        "  - Código limpo, tipado quando possível, com docstrings\n"
        "  - Error handling explícito (try/except com mensagens úteis)\n"
        "  - print() ou logging para diagnóstico\n"
        "  - Testar com casos simples antes de retornar\n\n"
        "REGRAS:\n"
        "  - Sem over-engineering: solução mais simples que funciona\n"
        "  - Sem código morto ou comentários óbvios\n"
        "  - Caminhos de arquivo: usar nomes diretos ex: output.py — NUNCA usar prefixo workspace/\n"
        "  - Imports no topo, sem importações dentro de funções\n"
    ),
)

# ── SKILL: DOCUMENT WRITER ────────────────────────────────────────────
SKILL_DOCUMENT = Skill(
    name="DOCUMENT_WRITER",
    description="Relatórios, contratos, documentação técnica, Word/DOCX",
    keywords=[
        "relatorio", "relatório", "documento", "word", "docx", ".docx",
        "contrato", "proposta comercial", "plano de negocio", "plano de negócio",
        "documentacao", "documentação", "manual", "guia", "readme",
        "especificacao", "especificação", "requisitos", "ata de reuniao",
        "memo", "carta", "oficio", "ofício", "laudo", "parecer",
        "escreva um texto", "redija", "elabore um", "crie um documento",
    ],
    excludes=["html", "css", "frontend", "landing", "slide", "powerpoint", "planilha"],
    priority=7,
    protocol=(
        "\n\n[SKILL ATIVO: DOCUMENT_WRITER]\n"
        "Você é um Redator Técnico de Elite. Para esta tarefa:\n\n"
        "FASE 1 — [PLANEJAMENTO]:\n"
        "  OBJETIVO: Qual decisão ou ação este documento vai gerar?\n"
        "  AUDIÊNCIA: Quem lê? Qual nível técnico? Qual contexto?\n"
        "  ESTRUTURA: Que seções são necessárias e em que ordem?\n"
        "  TOM: Formal/jurídico | Técnico/preciso | Executivo/direto\n\n"
        "FASE 2 — [ESCRITA]:\n"
        "  - Abertura que contextualiza em 1-2 frases\n"
        "  - Hierarquia clara: H1 > H2 > H3 com conteúdo substancial\n"
        "  - Linguagem ativa, sem passiva desnecessária\n"
        "  - Conclusão com ação esperada ou próximos passos\n\n"
        "REGRAS:\n"
        "  - Sem clichês corporativos ('sinergia', 'agregar valor')\n"
        "  - Tabelas para comparações, não para listas simples\n"
        "  - Números específicos são mais convincentes que adjetivos\n"
        "  - Se criar .docx: usar biblioteca python-docx, salvar com nome direto ex: relatorio.docx\n"
    ),
)

# ── SKILL: DATA ANALYST ───────────────────────────────────────────────
SKILL_DATA = Skill(
    name="DATA_ANALYST",
    description="Análise de dados, planilhas, visualizações, Excel/XLSX",
    keywords=[
        "planilha", "excel", "xlsx", ".xlsx", "csv", ".csv",
        "dados", "dataset", "dataframe", "pandas", "numpy",
        "analisar dados", "análise", "analise", "estatistica", "estatística",
        "grafico", "gráfico", "chart", "plot", "visualizacao", "visualização",
        "correlacao", "correlação", "regressao", "regressão", "tendencia",
        "media", "mediana", "desvio", "percentil", "histograma",
        "pivot", "tabela dinamica", "tabela dinâmica", "kpi", "metrica",
        "dashboard de dados", "relatorio de dados",
    ],
    excludes=["html", "css", "frontend", "landing"],
    priority=7,
    protocol=(
        "\n\n[SKILL ATIVO: DATA_ANALYST]\n"
        "Você é um Analista de Dados Sênior. Para esta tarefa:\n\n"
        "FASE 1 — [ENTENDIMENTO DOS DADOS]:\n"
        "  FONTE: Qual é o dado? Qual formato? Qual tamanho estimado?\n"
        "  PERGUNTA: Qual insight ou decisão esta análise vai suportar?\n"
        "  MÉTODO: Qual abordagem estatística é apropriada?\n"
        "  OUTPUT: Tabela | Gráfico | Relatório | Planilha Excel?\n\n"
        "FASE 2 — [ANÁLISE E VISUALIZAÇÃO]:\n"
        "  - Verificar dados nulos, outliers e inconsistências primeiro\n"
        "  - Comentar interpretação dos resultados, não só os números\n"
        "  - Gráficos com títulos, labels e unidades explícitas\n"
        "  - Conclusão acionável: 'Os dados sugerem que...'\n\n"
        "REGRAS:\n"
        "  - Se Excel: usar openpyxl, salvar com nome direto ex: dados.xlsx\n"
        "  - Evitar correlação sem causalidade — ser honesto sobre limitações\n"
        "  - print() com resumo dos resultados ao final\n"
    ),
)

# ── SKILL: PRESENTER ──────────────────────────────────────────────────
SKILL_PRESENTER = Skill(
    name="PRESENTER",
    description="Slides, pitch decks, apresentações PowerPoint/PPTX",
    keywords=[
        "apresentacao", "apresentação", "slide", "slides", "powerpoint",
        "pptx", ".pptx", "pitch", "pitch deck", "deck",
        "keynote", "apresentar", "palestrante",
    ],
    excludes=[],
    priority=9,
    protocol=(
        "\n\n[SKILL ATIVO: PRESENTER]\n"
        "Você é um Designer de Apresentações de Elite. Para esta tarefa:\n\n"
        "FASE 1 — [NARRATIVA]:\n"
        "  HISTÓRIA: Qual a jornada emocional do slide 1 ao último?\n"
        "  AUDIÊNCIA: Investidores | Clientes | Equipe | Técnica?\n"
        "  GANCHO: O que slide 1 promete que o último entrega?\n"
        "  ESTRUTURA: Problema → Solução → Evidência → Call to Action\n\n"
        "FASE 2 — [DESIGN DOS SLIDES]:\n"
        "  - 1 ideia por slide. Máximo 30 palavras de corpo por slide.\n"
        "  - Título que afirma, não descreve (Ex: 'Crescemos 3x' não 'Crescimento')\n"
        "  - Dados visuais: gráficos > tabelas > texto\n"
        "  - Consistência visual: mesma paleta, mesma tipografia\n\n"
        "REGRAS:\n"
        "  - Usar python-pptx, salvar com nome direto ex: apresentacao.pptx\n"
        "  - Sem bullet points em cascata (máximo 3 bullets por slide)\n"
        "  - print() com nome do arquivo e número de slides ao final\n"
    ),
)

# ── SKILL: PDF HANDLER ────────────────────────────────────────────────
SKILL_PDF = Skill(
    name="PDF_HANDLER",
    description="Manipulação, extração, formulários e criação de PDFs",
    keywords=[
        "pdf", ".pdf", "extrair texto", "extrair tabela",
        "combinar pdf", "dividir pdf", "preencher formulario",
        "formulario pdf", "assinar pdf", "marca dagua", "marca d'água",
        "ocr", "escanear", "digitalizar",
    ],
    excludes=[],
    priority=9,
    protocol=(
        "\n\n[SKILL ATIVO: PDF_HANDLER]\n"
        "Você é um Especialista em Manipulação de PDFs. Para esta tarefa:\n\n"
        "FASE 1 — [DIAGNÓSTICO]:\n"
        "  OPERAÇÃO: Extrair | Criar | Combinar | Dividir | Preencher | OCR?\n"
        "  FONTE: O PDF está na pasta atual? Qual o nome exato do arquivo? Qual o caminho exato?\n"
        "  OUTPUT: Qual o resultado esperado e onde salvar?\n\n"
        "FASE 2 — [EXECUÇÃO]:\n"
        "  - Usar pypdf2 ou pdfplumber dependendo da operação\n"
        "  - Para OCR: pytesseract com pré-processamento de imagem\n"
        "  - Verificar se o PDF é text-based ou image-based antes\n"
        "  - Salvar resultado com nome descritivo ex: resultado.pdf\n\n"
        "REGRAS:\n"
        "  - print() com path do arquivo criado e número de páginas\n"
        "  - Tratar PDFs protegidos com try/except explícito\n"
    ),
)

# ── SKILL: MCP BUILDER ────────────────────────────────────────────────
SKILL_MCP = Skill(
    name="MCP_BUILDER",
    description="Servidores MCP, tools, integrações com Claude",
    keywords=[
        "mcp", "model context protocol", "servidor mcp", "mcp server",
        "tool registration", "claude tool", "anthropic tool",
        "plugin para claude", "integrar com claude", "mcp tool",
    ],
    excludes=[],
    priority=10,
    protocol=(
        "\n\n[SKILL ATIVO: MCP_BUILDER]\n"
        "Você é um Especialista em Model Context Protocol. Para esta tarefa:\n\n"
        "FASE 1 — [DESIGN DO SERVIDOR]:\n"
        "  PROPÓSITO: Que capacidade este MCP adiciona ao Claude?\n"
        "  TOOLS: Quais tools (máximo 5 para começar)? Schemas Zod?\n"
        "  LINGUAGEM: TypeScript (padrão) ou Python?\n"
        "  TRANSPORTE: stdio | SSE | HTTP?\n\n"
        "FASE 2 — [IMPLEMENTAÇÃO]:\n"
        "  Estrutura obrigatória TypeScript:\n"
        "    package.json + tsconfig.json + src/index.ts\n"
        "  Estrutura obrigatória Python:\n"
        "    server.py + requirements.txt\n"
        "  - Cada tool com: name, description clara, inputSchema Zod/JSON\n"
        "  - Error handling: nunca retornar erro genérico\n"
        "  - README com instalação em 3 passos\n\n"
        "REGRAS:\n"
        "  - Tool names em snake_case\n"
        "  - Descriptions específicas (o LLM decide quando chamar pelo description)\n"
        "  - Salvar tudo em mcp-server/\n"
    ),
)

# ── SKILL: BRAND IDENTITY ─────────────────────────────────────────────
SKILL_BRAND = Skill(
    name="BRAND_IDENTITY",
    description="Identidade visual, guias de marca, logos, paletas",
    keywords=[
        "identidade visual", "marca", "branding", "logo", "logotipo",
        "guia de marca", "brand guide", "brand guidelines",
        "paleta de cores", "tipografia da marca", "manual de identidade",
        "estilo visual", "tom de voz da marca", "identidade de marca",
        "visual da marca", "guia visual",
    ],
    excludes=["landing", "codigo", "script", "html", "css"],
    priority=11,
    protocol=(
        "\n\n[SKILL ATIVO: BRAND_IDENTITY]\n"
        "Você é um Diretor de Arte especializado em Identidade de Marca. Para esta tarefa:\n\n"
        "FASE 1 — [DIAGNÓSTICO DE MARCA]:\n"
        "  PERSONALIDADE: Se a marca fosse uma pessoa, como seria?\n"
        "  VALORES: 3 palavras que a marca deve transmitir\n"
        "  PÚBLICO: Para quem? Em que contexto vão encontrar esta marca?\n"
        "  DIFERENCIAL: O que torna esta marca inconfundível?\n\n"
        "FASE 2 — [SISTEMA VISUAL]:\n"
        "  - Paleta primária (1-2 cores) + secundária (2-3) + neutros\n"
        "  - Tipografia: display + corpo + mono (se tech)\n"
        "  - Regras de uso: o que nunca fazer com a marca\n"
        "  - Exemplos de aplicação: digital, impresso, motion\n\n"
        "REGRAS:\n"
        "  - Justificar cada escolha em termos de percepção psicológica\n"
        "  - Entregar em HTML visual OU documento estruturado\n"
    ),
)

# ── SKILL: CREATIVE ART ───────────────────────────────────────────────
SKILL_ART = Skill(
    name="CREATIVE_ART",
    description="Arte generativa, canvas, visualizações matemáticas, fractais",
    keywords=[
        "arte generativa", "generative art", "fractal", "procedural",
        "canvas animation", "visualizacao matematica", "visualização matemática",
        "particle system", "sistema de particulas", "noise field",
        "l-system", "cellular automata", "shader", "glsl",
        "desenho algoritmico", "desenho algorítmico", "geometria",
        "animacao fractal", "animação fractal", "arte com canvas",
        "efeito visual generativo", "simulacao",
    ],
    excludes=["landing", "dashboard", "relatorio", "interface", "pagina"],
    priority=11,
    protocol=(
        "\n\n[SKILL ATIVO: CREATIVE_ART]\n"
        "Você é um Artista Generativo. Para esta tarefa:\n\n"
        "FASE 1 — [CONCEITO VISUAL]:\n"
        "  INSPIRAÇÃO: Qual fenômeno natural ou matemático?  \n"
        "  ALGORITMO: Qual sistema subjacente? (noise, L-system, autômato)\n"
        "  ESTÉTICA: Qual paleta e sensação? Orgânico | Geométrico | Caótico\n"
        "  INTERAÇÃO: Estático | Animado | Responsivo ao mouse?\n\n"
        "FASE 2 — [IMPLEMENTAÇÃO]:\n"
        "  - Canvas HTML5 com requestAnimationFrame\n"
        "  - Parâmetros como variáveis no topo (fácil tuning)\n"
        "  - Comentários explicando o algoritmo matemático\n"
        "  - Performance: máximo 60fps, sem memory leak\n\n"
        "REGRAS:\n"
        "  - Salvar como art.html diretamente (o Docker ja esta em /workspace)\n"
        "  - Sem triple-quoted strings — f.write() linha a linha\n"
        "  - print() confirmando criação ao final\n"
    ),
)

# ── SKILL: COMMUNICATOR ───────────────────────────────────────────────
SKILL_COMM = Skill(
    name="COMMUNICATOR",
    description="Comunicações internas, memos, newsletters, emails corporativos",
    keywords=[
        "email corporativo", "newsletter", "comunicado", "aviso",
        "memo interno", "nota interna", "comunicacao interna",
        "comunicação interna", "anuncio", "anúncio", "rh ",
        "mensagem para equipe", "mensagem para time",
        "escreva um email", "redija um email",
        "comunicado interno", "nota para equipe", "circular",
    ],
    excludes=["codigo", "html", "frontend", "script", "processo de software", "pipeline"],
    priority=11,
    protocol=(
        "\n\n[SKILL ATIVO: COMMUNICATOR]\n"
        "Você é um Especialista em Comunicação Corporativa. Para esta tarefa:\n\n"
        "FASE 1 — [INTENÇÃO]:\n"
        "  OBJETIVO: Informar | Convencer | Motivar | Alertar?\n"
        "  TOM: Formal | Próximo | Urgente | Celebratório?\n"
        "  AÇÃO ESPERADA: O que o leitor deve fazer após ler?\n\n"
        "FASE 2 — [ESCRITA]:\n"
        "  - Assunto/título que explica o valor, não o tema\n"
        "    Ruim: 'Atualização de Processo' | Bom: 'Novo processo reduz 40% do tempo'\n"
        "  - Primeiro parágrafo: o essencial em 2 frases\n"
        "  - Corpo: contexto + detalhes + call to action\n"
        "  - Fecho: próximo passo claro com deadline se houver\n\n"
        "REGRAS:\n"
        "  - Sem linguagem passiva excessiva\n"
        "  - Sem jargão desnecessário\n"
        "  - Parágrafos curtos (máximo 4 linhas)\n"
    ),
)


# ══════════════════════════════════════════════════════════════════════
# O ROTEADOR
# ══════════════════════════════════════════════════════════════════════

ALL_SKILLS = [
    SKILL_FRONTEND,
    SKILL_SOFTWARE,
    SKILL_DOCUMENT,
    SKILL_DATA,
    SKILL_PRESENTER,
    SKILL_PDF,
    SKILL_MCP,
    SKILL_BRAND,
    SKILL_ART,
    SKILL_COMM,
]


class SkillRouter:
    """
    Sistema nervoso cognitivo do KOSMOS.

    Analisa a intenção de qualquer tarefa e injeta o protocolo
    correto no system prompt — sem overhead para tarefas sem match.

    Exemplo:
        router = SkillRouter()
        protocol = router.route("Crie uma landing page para CNGSM")
        # → retorna SKILL_FRONTEND.protocol

        protocol = router.route("Corrija o bug no script de análise")
        # → retorna SKILL_SOFTWARE.protocol

        protocol = router.route("Qual a capital do Brasil?")
        # → retorna "" (nenhum skill, sem overhead)
    """

    def __init__(self, skills: list = None, verbose: bool = True):
        self.skills = skills or ALL_SKILLS
        self.verbose = verbose
        self._cache = {}

    def route(self, task: str) -> str:
        """
        Analisa a tarefa e retorna o protocolo do skill mais adequado.
        Retorna string vazia se nenhum skill combinar.
        """
        if not task or not task.strip():
            return ""

        # Cache simples para evitar re-análise da mesma tarefa
        cache_key = task[:100].lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        task_lower = task.lower()
        matches = []

        for skill in self.skills:
            # Verifica exclusões primeiro
            if any(ex in task_lower for ex in skill.excludes):
                continue

            # Conta keywords que batem
            hits = sum(1 for kw in skill.keywords if kw in task_lower)
            if hits > 0:
                score = hits * 10 + skill.priority
                matches.append((score, skill))

        if not matches:
            if self.verbose:
                logger.debug(f"SkillRouter: nenhum skill para '{task[:60]}...'")
            self._cache[cache_key] = ""
            return ""

        # Skill com maior score
        matches.sort(key=lambda x: x[0], reverse=True)
        best_score, best_skill = matches[0]

        if self.verbose:
            logger.info(
                f"SkillRouter: '{task[:50]}...' → {best_skill.name} "
                f"(score={best_score}, matches={[s.name for _, s in matches[:3]]})"
            )

        result = best_skill.protocol
        self._cache[cache_key] = result
        return result

    def route_all(self, task: str) -> list:
        """
        Retorna todos os skills que combinam com a tarefa, ordenados por score.
        Útil para debug e para tarefas híbridas (ex: 'dashboard de dados' pode
        precisar de FRONTEND + DATA juntos).
        """
        task_lower = task.lower()
        matches = []

        for skill in self.skills:
            if any(ex in task_lower for ex in skill.excludes):
                continue
            hits = sum(1 for kw in skill.keywords if kw in task_lower)
            if hits > 0:
                score = hits * 10 + skill.priority
                matches.append((score, skill))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [(score, skill.name, skill.description) for score, skill in matches]

    def explain(self, task: str) -> str:
        """Explica o processo de roteamento para debug."""
        matches = self.route_all(task)
        if not matches:
            return f"Tarefa: '{task}'\nResultado: Nenhum skill ativado (base prompt apenas)"

        lines = [f"Tarefa: '{task}'", "Roteamento:"]
        for i, (score, name, desc) in enumerate(matches):
            prefix = "  → SELECIONADO:" if i == 0 else "     alternativo:"
            lines.append(f"{prefix} [{name}] score={score} — {desc}")
        return "\n".join(lines)

    def add_skill(self, skill: Skill):
        """Adiciona um skill customizado em runtime."""
        self.skills.append(skill)
        self._cache.clear()
        logger.info(f"SkillRouter: skill '{skill.name}' adicionado")

    def list_skills(self) -> list:
        """Lista todos os skills registrados."""
        return [(s.name, s.description, s.priority) for s in self.skills]


# ══════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM O KOSMOS ENGINE
# ══════════════════════════════════════════════════════════════════════
#
# Em agents.py ou planner_tot.py, substitua a construção do system
# prompt do Proposer por:
#
#   from skill_router import SkillRouter
#   _skill_router = SkillRouter()  # instância única (singleton)
#
#   def build_proposer_prompt(task: str, base_prompt: str) -> str:
#       return base_prompt + _skill_router.route(task)
#
#   messages = [
#       {'role': 'system', 'content': build_proposer_prompt(task, BASE_PROMPT)},
#       {'role': 'user',   'content': task},
#   ]
#
# Para tarefas híbridas (ex: dashboard que precisa de dados + visual):
#
#   def build_hybrid_prompt(task: str, base_prompt: str) -> str:
#       matches = _skill_router.route_all(task)
#       if len(matches) >= 2 and matches[0][0] - matches[1][0] < 15:
#           # Empate próximo = tarefa híbrida, injeta os 2 principais
#           skills_by_name = {s.name: s for s in ALL_SKILLS}
#           combined = base_prompt
#           for _, name, _ in matches[:2]:
#               combined += skills_by_name[name].protocol
#           return combined
#       return base_prompt + _skill_router.route(task)


# ══════════════════════════════════════════════════════════════════════
# EXECUÇÃO DIRETA — TESTES E DEMONSTRAÇÃO
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    router = SkillRouter(verbose=False)

    print("\n" + "=" * 60)
    print("KOSMOS SkillRouter — Teste de Roteamento")
    print("=" * 60)

    test_cases = [
        # (tarefa, skill_esperado_ou_None)
        ("Crie uma landing page para CNGSM com animações neurais", "FRONTEND_DESIGN"),
        ("Corrija o bug no script Python de análise de logs",       "SOFTWARE_ENGINEER"),
        ("Faça um dashboard de métricas de vendas",                 "FRONTEND_DESIGN"),
        ("Crie um relatório executivo em Word sobre o projeto",     "DOCUMENT_WRITER"),
        ("Analise este CSV de vendas e gere gráficos",              "DATA_ANALYST"),
        ("Monte uma apresentação de pitch para investidores",       "PRESENTER"),
        ("Extraia o texto deste PDF de contrato",                   "PDF_HANDLER"),
        ("Construa um servidor MCP para integrar o KOSMOS",        "MCP_BUILDER"),
        ("Desenvolva o guia de identidade visual da CNGSM",        "BRAND_IDENTITY"),
        ("Crie uma animação fractal com canvas HTML5",              "CREATIVE_ART"),
        ("Escreva um comunicado interno sobre o novo processo",     "COMMUNICATOR"),
        ("Execute um web scraper para coletar preços",              "SOFTWARE_ENGINEER"),
        ("Qual a diferença entre TCP e UDP?",                       None),
        ("Crie um dashboard de dados com gráficos interativos",     "DATA_ANALYST"),   # híbrido: DATA wins por keyword score
    ]

    correct = 0
    total = len(test_cases)

    for task, expected in test_cases:
        matches = router.route_all(task)
        selected = matches[0][1] if matches else None
        ok = selected == expected
        correct += ok
        status = "OK  " if ok else "FAIL"
        exp_str = expected or "—"
        sel_str = selected or "—"
        eq = "=" if ok else "≠"
        print(f"  [{status}]  {task[:50]:<50}  {exp_str:<20} {eq} {sel_str}")

    print()
    print(f"Resultado: {correct}/{total} corretos")
    print()

    # Demonstração do explain()
    print("=" * 60)
    print("Exemplo de explain() para tarefa híbrida:")
    print(router.explain("Dashboard de dados com gráficos interativos e bom visual"))
    print()

    # Lista todos os skills
    print("=" * 60)
    print("Skills registrados:")
    for name, desc, priority in router.list_skills():
        print(f"  [{priority:2d}] {name:<20} — {desc}")
    print("=" * 60 + "\n")
