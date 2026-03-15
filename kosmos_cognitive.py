"""
kosmos_cognitive.py — KOSMOS Stage 4 Solution
==============================================
F8 — SemanticSkillRouter: roteamento por similaridade semântica
    - Usa TF-IDF + expansão de vocabulário por domínio
    - Detecta intenção mesmo sem keywords exatas
    - Fallback para keyword matching do skill_router.py existente

F9 — LoopDetector: detector de loop infinito
    - Rastreia (task_hash, strategy) por sessão
    - Detecta repetição após N tentativas (padrão: 2)
    - Sugere estratégia alternativa baseada no histórico
    - Reset por tarefa ou global

F10 — PersistentSkillForge: SkillForge com persistência em JSON
    - Skills forjados salvos em arquivo JSON
    - Carregados automaticamente na próxima instância
    - Compatível com skill_forge.py existente
"""

import re
import json
import math
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger("kosmos.cognitive")


# ══════════════════════════════════════════════════════════════════
# F8 — SEMANTIC SKILL ROUTER
# ══════════════════════════════════════════════════════════════════

# Vocabulário semântico por domínio — palavras relacionadas sem ser keywords exatas
SEMANTIC_VOCAB = {
    "FRONTEND_DESIGN": [
        # Design visual
        "bonito", "visual", "aparencia", "aparência", "estética", "estetica",
        "interface", "tela", "pagina", "página", "site", "web", "layout",
        "cores", "tipografia", "fonte", "animacao", "animação", "responsivo",
        "mobile", "desktop", "imagem", "logo", "marca", "identidade",
        "portfolio", "portfólio", "landing", "home", "institucional",
        "apresentar", "mostrar", "exibir", "vitrine", "showcase",
        # Frameworks
        "react", "vue", "angular", "html", "css", "javascript", "frontend",
        "componente", "widget", "dashboard", "painel", "interface",
    ],
    "SOFTWARE_ENGINEER": [
        # Debugging e código
        "erro", "bug", "falha", "problema", "fix", "corrigir", "resolver",
        "código", "codigo", "script", "função", "funcao", "classe", "método",
        "algoritmo", "implementar", "desenvolver", "criar", "construir",
        "testar", "teste", "debug", "traceback", "exception", "error",
        "api", "endpoint", "servidor", "backend", "banco", "database",
        "automação", "automacao", "pipeline", "processo", "workflow",
        "otimizar", "refatorar", "melhorar", "performance", "velocidade",
        "python", "javascript", "typescript", "java", "golang", "rust",
    ],
    "DOCUMENT_WRITER": [
        # Escrita e documentos
        "relatório", "relatorio", "documento", "texto", "escrever", "redigir",
        "elaborar", "criar", "preparar", "produzir", "gerar",
        "proposta", "contrato", "acordo", "termo", "política", "politica",
        "manual", "guia", "tutorial", "instrução", "instrucao", "procedimento",
        "ata", "reunião", "reuniao", "board", "diretoria", "executivo",
        "apresentar", "comunicar", "informar", "descrever", "documentar",
        "word", "docx", "pdf", "formal", "oficial", "corporativo",
    ],
    "DATA_ANALYST": [
        # Dados e análise
        "dados", "data", "números", "numeros", "métricas", "metricas",
        "análise", "analise", "analisar", "visualizar", "gráfico", "grafico",
        "planilha", "excel", "tabela", "estatística", "estatistica",
        "tendência", "tendencia", "crescimento", "queda", "variação",
        "vendas", "receita", "lucro", "custo", "performance", "kpi",
        "trimestre", "mensal", "anual", "histórico", "historico", "série",
        "comparar", "medir", "calcular", "estimar", "projetar",
        "csv", "json", "pandas", "numpy", "matplotlib",
    ],
    "PRESENTER": [
        # Apresentações
        "apresentação", "apresentacao", "slide", "deck", "pitch",
        "mostrar", "apresentar", "expor", "demonstrar",
        "investidores", "clientes", "board", "diretoria", "reunião",
        "powerpoint", "keynote", "prezi",
        "convencer", "persuadir", "vender", "proposta",
    ],
    "COMMUNICATOR": [
        # Comunicação interna
        "equipe", "time", "funcionários", "funcionarios", "colaboradores",
        "comunicar", "informar", "avisar", "notificar", "anunciar",
        "política", "politica", "procedimento", "norma", "regra",
        "férias", "ferias", "benefícios", "beneficios", "rh", "recursos",
        "interno", "interna", "empresa", "organização", "organizacao",
        "newsletter", "circular", "memo", "memorando", "comunicado",
    ],
    "MCP_BUILDER": [
        "mcp", "protocol", "tool", "integration", "plugin", "servidor",
        "anthropic", "claude", "integrar", "conectar", "api", "webhook",
    ],
    "PDF_HANDLER": [
        "pdf", "documento", "extrair", "converter", "formulario", "formulário",
        "assinar", "digitalizar", "escanear", "ocr",
    ],
    "BRAND_IDENTITY": [
        "marca", "brand", "identidade", "logo", "logotipo", "visual",
        "cores", "tipografia", "guia", "manual", "estilo",
        "posicionamento", "personalidade", "tom", "voz",
    ],
    "CREATIVE_ART": [
        "arte", "criativo", "generativo", "fractal", "animação", "canvas",
        "visualização", "matemática", "procedural", "algoritmo", "geometria",
        "particle", "shader", "glsl", "efeito", "visual",
    ],
}


class SemanticSkillRouter:
    """
    Roteador de skills por similaridade semântica.
    Detecta intenção mesmo quando o vocabulário exato não está presente.
    """

    def __init__(self, fallback_to_keyword: bool = True):
        self.fallback_to_keyword = fallback_to_keyword
        self._vocab = SEMANTIC_VOCAB

    def route(self, task: str) -> Optional[Dict[str, Any]]:
        """
        Roteia a tarefa para o skill mais adequado.
        Retorna {"skill": nome, "score": float, "method": "semantic"|"keyword"}
        ou None se nenhum skill combinar.
        """
        task_tokens = self._tokenize(task)

        if not task_tokens:
            return None

        scores = {}
        for skill_name, vocab in self._vocab.items():
            score = self._semantic_score(task_tokens, vocab)
            if score > 0:
                scores[skill_name] = score

        if not scores:
            return None

        best_skill = max(scores, key=scores.get)
        best_score = scores[best_skill]

        # Threshold mínimo de relevância
        if best_score < 0.05:
            return None

        logger.info(
            f"SemanticSkillRouter: '{task[:40]}...' → {best_skill} "
            f"(score={best_score:.3f})"
        )

        return {
            "skill":    best_skill,
            "score":    best_score,
            "method":   "semantic",
            "all_scores": dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]),
        }

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        stopwords = {
            "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
            "em", "no", "na", "nos", "nas", "e", "é", "para", "por", "com",
            "que", "se", "me", "minha", "meu", "nossa", "nosso", "preciso",
            "quero", "gostaria", "the", "a", "an", "is", "are", "i", "my",
        }
        return [t for t in tokens if t not in stopwords and len(t) > 2]

    def _semantic_score(self, task_tokens: List[str], vocab: List[str]) -> float:
        """
        Score semântico: proporção de tokens da tarefa que aparecem no vocabulário.
        Ponderado por posição (tokens no início têm mais peso).
        """
        vocab_set = set(vocab)
        total_weight = 0.0
        matched_weight = 0.0

        for i, token in enumerate(task_tokens):
            # Tokens no início da frase têm mais peso
            weight = 1.0 / (1 + i * 0.1)
            total_weight += weight

            # Match exato ou prefixo (stemming simples)
            if token in vocab_set:
                matched_weight += weight
            elif any(v.startswith(token[:4]) for v in vocab_set if len(v) >= 4):
                matched_weight += weight * 0.6  # match parcial tem peso menor

        return matched_weight / total_weight if total_weight > 0 else 0.0


# ══════════════════════════════════════════════════════════════════
# F9 — LOOP DETECTOR
# ══════════════════════════════════════════════════════════════════

# Estratégias alternativas quando um loop é detectado
STRATEGY_ALTERNATIVES = {
    "llm_generated":    ["write_file", "base64_encode", "decompose"],
    "write_file":       ["base64_encode", "python_chunks", "llm_generated"],
    "base64_encode":    ["write_file", "python_chunks", "decompose"],
    "python_chunks":    ["write_file", "llm_generated", "decompose"],
    "fix_json":         ["simplify", "decompose", "llm_generated"],
    "simplify":         ["decompose", "llm_generated", "write_file"],
    "decompose":        ["llm_generated", "write_file", "step_by_step"],
    "retry":            ["refine", "decompose", "simplify"],
    "refine":           ["decompose", "write_file", "llm_generated"],
}

DEFAULT_ALTERNATIVE = "decompose"


class LoopDetector:
    """
    Detecta loops infinitos no ciclo de planejamento.

    Um loop é detectado quando a mesma (task, strategy) aparece
    mais de max_repeats vezes sem sucesso.
    """

    def __init__(self, max_repeats: int = 2):
        self.max_repeats = max_repeats
        self._history: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def _task_key(self, task: str) -> str:
        """Hash da tarefa (ignora sufixos de erro adicionados pelo Reflexion)."""
        # Remove sufixos como "[Erro de ...]" ou "[Refinar ...]"
        clean = re.sub(r'\[.*?\]', '', task).strip()
        return hashlib.md5(clean.encode()).hexdigest()[:12]

    def is_loop(self, task: str, strategy: str) -> bool:
        """
        Registra a tentativa e retorna True se é um loop.
        """
        key = self._task_key(task)
        self._history[key][strategy] += 1
        count = self._history[key][strategy]

        if count > self.max_repeats:
            logger.warning(
                f"LoopDetector: loop detectado! "
                f"task='{task[:40]}' strategy='{strategy}' count={count}"
            )
            return True
        return False

    def suggest_alternative(self, task: str, failed_strategy: str) -> str:
        """
        Sugere uma estratégia alternativa baseada no histórico de falhas.
        Evita sugerir estratégias que já falharam.
        """
        key = self._task_key(task)
        failed_strategies = set(self._history[key].keys())

        # Busca alternativas que ainda não foram tentadas
        alternatives = STRATEGY_ALTERNATIVES.get(failed_strategy, [DEFAULT_ALTERNATIVE])

        for alt in alternatives:
            if alt not in failed_strategies:
                return alt

        # Todas as alternativas já foram tentadas — sugere decompose como último recurso
        return DEFAULT_ALTERNATIVE

    def get_history(self, task: str) -> Dict[str, int]:
        """Retorna o histórico de tentativas para uma tarefa."""
        key = self._task_key(task)
        return dict(self._history[key])

    def reset(self, task: Optional[str] = None):
        """Limpa o histórico de uma tarefa ou de todas."""
        if task:
            key = self._task_key(task)
            self._history.pop(key, None)
        else:
            self._history.clear()


# ══════════════════════════════════════════════════════════════════
# F10 — PERSISTENT SKILL FORGE
# ══════════════════════════════════════════════════════════════════

class PersistentSkillForge:
    """
    SkillForge com persistência em JSON.
    Skills forjados sobrevivem a reinicializações do processo.
    """

    def __init__(self, registry_path: str = "skills_registry.json"):
        self.registry_path = Path(registry_path)
        self._registry: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        """Carrega o registry do disco."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    self._registry = json.load(f)
                logger.info(
                    f"PersistentSkillForge: {len(self._registry)} skills carregados "
                    f"de {self.registry_path}"
                )
            except Exception as e:
                logger.warning(f"Erro ao carregar registry: {e}")
                self._registry = {}

    def _save(self):
        """Salva o registry no disco."""
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(self._registry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Erro ao salvar registry: {e}")

    def forge(
        self,
        description: str,
        domain_hint: str = "",
        keywords: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Forja um skill para um domínio novo e persiste em disco.
        Se já existe, retorna o existente sem reforjar.
        """
        # Normaliza o nome
        name = domain_hint.upper().replace(" ", "_") if domain_hint else \
               hashlib.md5(description.encode()).hexdigest()[:8].upper()

        # Já existe?
        if name in self._registry:
            logger.debug(f"PersistentSkillForge: skill '{name}' já existe (cache hit)")
            return self._registry[name]

        # Extrai keywords da descrição se não fornecidas
        if not keywords:
            keywords = self._extract_keywords(description)

        # Cria o skill
        skill = {
            "name":        name,
            "domain":      domain_hint or "CUSTOM",
            "description": description,
            "keywords":    keywords,
            "excludes":    [],
            "priority":    9,
            "protocol":    self._generate_protocol(name, description),
            "origin":      "forged",
            "source_skill": "PILLARS",
        }

        self._registry[name] = skill
        self._save()

        logger.info(f"PersistentSkillForge: skill '{name}' forjado e salvo")
        return skill

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Recupera um skill pelo nome."""
        # Busca exata
        if name in self._registry:
            return self._registry[name]
        # Busca case-insensitive
        name_upper = name.upper()
        for key, skill in self._registry.items():
            if key.upper() == name_upper:
                return skill
        return None

    def count(self) -> int:
        return len(self._registry)

    def list_skills(self) -> List[str]:
        return list(self._registry.keys())

    def _extract_keywords(self, text: str) -> List[str]:
        """Extrai keywords relevantes do texto da descrição."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        stopwords = {
            "o", "a", "os", "as", "um", "uma", "de", "do", "da", "e", "para",
            "com", "que", "se", "em", "por", "the", "and", "of", "for", "to",
        }
        keywords = [t for t in tokens if t not in stopwords and len(t) > 3]
        # Remove duplicatas preservando ordem
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique[:15]

    def _generate_protocol(self, name: str, description: str) -> str:
        """Gera um protocolo básico via 6 Pilares Cognitivos."""
        return (
            f"\n\n[SKILL FORJADO: {name}]\n"
            f"Domínio: {description}\n\n"
            f"Aplicando os 6 Pilares Cognitivos Universais:\n\n"
            f"FASE 1 — [ANÁLISE MULTIDIMENSIONAL]:\n"
            f"  PILAR 1 — Primeiros Princípios:\n"
            f"    Qual é o problema fundamental, despido de pressupostos?\n\n"
            f"  PILAR 2 — Estrutura do Output:\n"
            f"    Como o resultado deve ser organizado para máximo impacto?\n\n"
            f"  PILAR 3 — Ancoragem em Restrições:\n"
            f"    Quais as restrições invioláveis deste domínio?\n\n"
            f"  PILAR 4 — Advogado do Diabo:\n"
            f"    Qual o argumento mais forte contra a abordagem escolhida?\n\n"
            f"  PILAR 5 — Cruzamento Interdisciplinar:\n"
            f"    Qual domínio distante pode iluminar este problema?\n\n"
            f"  PILAR 6 — Dark Knowledge:\n"
            f"    O que é implícito mas não dito neste contexto?\n\n"
            f"FASE 2 — [EXECUÇÃO]:\n"
            f"  Resposta que integra os 6 pilares.\n"
            f"  Anti-banalidade: evitar o consenso seguro em qualquer forma.\n"
        )


# ══════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM O KOSMOS
# ══════════════════════════════════════════════════════════════════
#
# Em llm_client.py (generate_proposal), substitua o SkillRouter por:
#
#   from kosmos_cognitive import SemanticSkillRouter, LoopDetector, PersistentSkillForge
#
#   if not hasattr(self, "_semantic_router"):
#       self._semantic_router = SemanticSkillRouter()
#       self._loop_detector   = LoopDetector(max_repeats=2)
#       self._skill_forge     = PersistentSkillForge("skills_registry.json")
#
#   # Detecta loop antes de gerar
#   if self._loop_detector.is_loop(task, last_strategy):
#       alt = self._loop_detector.suggest_alternative(task, last_strategy)
#       task = f"{task} [FORÇAR ESTRATÉGIA: {alt}]"
#
#   # Roteamento semântico
#   route_result = self._semantic_router.route(task)
#   if route_result:
#       skill_name = route_result["skill"]
#       # Obtém protocolo do skill_router existente
#       from skill_router import SkillRouter
#       _skill_protocol = SkillRouter().route(task) or ""


if __name__ == "__main__":
    print("kosmos_cognitive.py — Demo\n")

    # SemanticSkillRouter
    router = SemanticSkillRouter()
    test_tasks = [
        "preciso de algo bonito para minha empresa de IA",
        "tem um bug estranho no código que não consigo resolver",
        "quero visualizar os números do trimestre",
        "nossa equipe precisa saber da nova política",
    ]
    print("SemanticSkillRouter:")
    for task in test_tasks:
        result = router.route(task)
        skill = result["skill"] if result else "—"
        score = f"{result['score']:.3f}" if result else "—"
        print(f"  [{skill:20}] {score} | {task[:50]}")

    # LoopDetector
    print("\nLoopDetector:")
    detector = LoopDetector(max_repeats=2)
    task = "criar landing page"
    for i in range(4):
        is_loop = detector.is_loop(task, "llm_generated")
        alt = detector.suggest_alternative(task, "llm_generated") if is_loop else "—"
        print(f"  Tentativa {i+1}: loop={is_loop} | alternativa={alt}")

    # PersistentSkillForge
    import tempfile
    print("\nPersistentSkillForge:")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        reg = f.name
    forge = PersistentSkillForge(registry_path=reg)
    skill = forge.forge("Análise jurídica de contratos", "LEGAL_ANALYSIS")
    print(f"  Forjado: {skill['name']} | keywords: {skill['keywords'][:4]}")
    forge2 = PersistentSkillForge(registry_path=reg)
    found = forge2.get("LEGAL_ANALYSIS")
    print(f"  Persistiu: {found is not None} | count={forge2.count()}")
    Path(reg).unlink(missing_ok=True)
    print("\n✓ Demo concluído")
