"""
KOSMOS Agent — Mixture of Agents (Proposer + Reviewer) — LLM-Powered
=====================================================================
Proposer gera planos de ação usando DeepSeek LLM.
Reviewer pontua propostas com LLM + heurísticas.
Fallback para templates se LLM offline.
"""

import random
import logging
from typing import Dict, Any, List, Optional

from llm_client import DeepSeekClient, LLMConfig, get_llm_client

logger = logging.getLogger("kosmos.agents")


class ProposerAgent:
    """
    Agente Propositor com LLM DeepSeek.

    Modo LLM:  gera código real via DeepSeek API
    Modo local: fallback para templates quando LLM offline

    Cada chamada a propose() gera uma variacao do plano,
    permitindo exploracao no Tree of Thoughts.
    """

    STRATEGIES = [
        {
            "name": "direct_computation",
            "thought": "Executar cálculo direto via Python",
            "approach": "Resolver com operações matemáticas padrão",
        },
        {
            "name": "algorithmic",
            "thought": "Implementar algoritmo específico para o problema",
            "approach": "Usar estruturas de dados e algoritmos clássicos",
        },
        {
            "name": "library_based",
            "thought": "Usar bibliotecas Python especializadas",
            "approach": "Aproveitar numpy, scipy, ou outras libs",
        },
        {
            "name": "decomposition",
            "thought": "Decompor em subproblemas menores",
            "approach": "Resolver cada parte e combinar resultados",
        },
    ]

    def __init__(
        self,
        llm_client: Optional[DeepSeekClient] = None,
        use_llm: bool = True,
        seed: Optional[int] = None,
    ):
        self.rng = random.Random(seed)
        self.proposal_count = 0
        self.use_llm = use_llm
        self._llm = llm_client

    @property
    def llm(self) -> DeepSeekClient:
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    def propose(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Gera uma proposta de ação para a tarefa.
        Tenta LLM primeiro, fallback para templates.
        """
        self.proposal_count += 1

        # ─── Tenta LLM ───
        if self.use_llm:
            try:
                llm_result = self._propose_with_llm(task, context)
                if llm_result and llm_result.get("code"):
                    llm_result["id"] = self.proposal_count
                    llm_result["tool"] = "python"
                    llm_result["source"] = "deepseek_llm"
                    logger.info(
                        f"Proposta #{self.proposal_count}: LLM "
                        f"(strategy={llm_result.get('strategy', 'llm')})"
                    )
                    return llm_result
            except Exception as e:
                logger.warning(f"LLM falhou, usando fallback: {e}")

        # ─── Fallback: templates locais ───
        return self._propose_with_templates(task, context)

    def _propose_with_llm(
        self, task: str, context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Gera proposta usando DeepSeek LLM."""
        context_str = None
        if context:
            recent = context.get("recent_episodes", [])
            if recent:
                # Formata episódios recentes como contexto
                parts = []
                for ep in recent[-3:]:
                    critique = ep.get("critique", {})
                    parts.append(
                        f"- Task: {ep.get('task', '')}, "
                        f"Success: {critique.get('success', '?')}, "
                        f"Feedback: {critique.get('feedback', '')[:100]}"
                    )
                context_str = "Tentativas anteriores:\n" + "\n".join(parts)

        result = self.llm.generate_proposal(task, context_str)
        return result

    def _propose_with_templates(
        self, task: str, context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Fallback: gera proposta usando templates locais."""
        strategy_idx = (self.proposal_count - 1) % len(self.STRATEGIES)
        strategy = self.STRATEGIES[strategy_idx]

        code = self._generate_code(task, strategy, context)

        proposal = {
            "id": self.proposal_count,
            "thought": f"[{strategy['name']}] {strategy['thought']}: {task}",
            "approach": strategy["approach"],
            "tool": "python",
            "code": code,
            "strategy": strategy["name"],
            "source": "template_fallback",
        }

        logger.debug(
            f"Proposta #{self.proposal_count} (template): "
            f"strategy={strategy['name']}"
        )
        return proposal

    def _generate_code(
        self, task: str, strategy: Dict, context: Optional[Dict] = None
    ) -> str:
        """Gera código via templates (fallback)."""
        task_lower = task.lower()

        if "calcul" in task_lower or "comput" in task_lower:
            return self._code_for_calculation(task, strategy)
        elif "fibonacci" in task_lower:
            return self._code_for_fibonacci(strategy)
        elif "sort" in task_lower or "orden" in task_lower:
            return self._code_for_sorting(strategy)
        elif "busca" in task_lower or "search" in task_lower:
            return self._code_for_search(strategy)
        else:
            return self._code_generic(task, strategy)

    def _code_for_calculation(self, task: str, strategy: Dict) -> str:
        if strategy["name"] == "library_based":
            return (
                "import math\n"
                f"# {task}\n"
                "result = eval(input_expr) if 'input_expr' in dir() else 2 + 2\n"
                "print(f'Resultado: {result}')"
            )
        return (
            f"# {task}\n"
            "result = 2 + 2\n"
            "print(f'Resultado: {result}')"
        )

    def _code_for_fibonacci(self, strategy: Dict) -> str:
        if strategy["name"] == "algorithmic":
            return (
                "def fib(n):\n"
                "    if n <= 1: return n\n"
                "    a, b = 0, 1\n"
                "    for _ in range(2, n + 1):\n"
                "        a, b = b, a + b\n"
                "    return b\n\n"
                "result = [fib(i) for i in range(10)]\n"
                "print(f'Fibonacci: {result}')"
            )
        return (
            "def fib(n):\n"
            "    if n <= 1: return n\n"
            "    return fib(n-1) + fib(n-2)\n\n"
            "result = [fib(i) for i in range(10)]\n"
            "print(f'Fibonacci: {result}')"
        )

    def _code_for_sorting(self, strategy: Dict) -> str:
        if strategy["name"] == "library_based":
            return (
                "import random\n"
                "data = [random.randint(1, 100) for _ in range(10)]\n"
                "result = sorted(data)\n"
                "print(f'Sorted: {result}')"
            )
        return (
            "data = [64, 34, 25, 12, 22, 11, 90]\n"
            "for i in range(len(data)):\n"
            "    for j in range(0, len(data)-i-1):\n"
            "        if data[j] > data[j+1]:\n"
            "            data[j], data[j+1] = data[j+1], data[j]\n"
            "result = data\n"
            "print(f'Sorted: {result}')"
        )

    def _code_for_search(self, strategy: Dict) -> str:
        return (
            "data = list(range(1, 101))\n"
            "target = 42\n"
            "lo, hi = 0, len(data) - 1\n"
            "while lo <= hi:\n"
            "    mid = (lo + hi) // 2\n"
            "    if data[mid] == target:\n"
            "        break\n"
            "    elif data[mid] < target:\n"
            "        lo = mid + 1\n"
            "    else:\n"
            "        hi = mid - 1\n"
            "result = mid\n"
            "print(f'Encontrado {target} na posição {result}')"
        )

    def _code_generic(self, task: str, strategy: Dict) -> str:
        # Sanitiza a tarefa para o comentário (remove novas linhas)
        clean_task = task.replace("\n", " ").replace("\r", "")
        # Usa repr() para garantir que a string seja embutida com escape perfeito no código
        safe_task_repr = repr(f"[AUTO-DEV] Warning: Plano genérico executado para: {task}")
        return (
            f"# Tarefa: {clean_task[:100]}...\n"
            f"# Estratégia: {strategy['name']}\n"
            f"result = {safe_task_repr}\n"
            "print(result)"
        )


class ReviewerAgent:
    """
    Agente Revisor com LLM DeepSeek + heurísticas.

    Modo LLM: revisão semântica via DeepSeek
    Modo local: scoring baseado em heuristicas (5 criterios)
    """

    def __init__(
        self,
        llm_client: Optional[DeepSeekClient] = None,
        use_llm: bool = True,
    ):
        self.reviews: List[Dict] = []
        self.use_llm = use_llm
        self._llm = llm_client
        self._task: str = ""  # task corrente (set pelo planner)

    @property
    def llm(self) -> DeepSeekClient:
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    def set_task(self, task: str):
        """Define a task corrente para contexto na revisão."""
        self._task = task

    def review(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Revisa proposta: LLM + heurísticas combinados.
        Score final = media ponderada (LLM 60% + heuristica 40%).
        """
        heuristic_result = self._heuristic_review(proposal)

        if self.use_llm and self._task:
            try:
                llm_result = self._llm_review(proposal)
                if llm_result and "score" in llm_result:
                    # Combina scores
                    combined_score = (
                        llm_result["score"] * 0.6
                        + heuristic_result["score"] * 0.4
                    )
                    review_result = {
                        "score": round(combined_score, 2),
                        "feedback": (
                            f"[LLM] {llm_result.get('feedback', '')} | "
                            f"[Heuristic] {heuristic_result['feedback']}"
                        ),
                        "approved": combined_score >= 0.5,
                        "proposal_id": proposal.get("id", "unknown"),
                        "source": "llm+heuristic",
                        "improvements": llm_result.get("improvements", []),
                    }
                    self.reviews.append(review_result)
                    return review_result
            except Exception as e:
                logger.warning(f"LLM review falhou: {e}")

        # Fallback: apenas heurísticas
        heuristic_result["source"] = "heuristic_only"
        self.reviews.append(heuristic_result)
        return heuristic_result

    def _llm_review(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Revisão via DeepSeek LLM."""
        return self.llm.review_proposal(self._task, proposal)

    def _heuristic_review(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Revisao via heuristicas locais (5 criterios)."""
        score = 0.0
        feedback_parts = []

        # Criterio 1: Presenca de codigo (0.3)
        if "code" in proposal and proposal["code"].strip():
            score += 0.3
            feedback_parts.append("✓ Código")
        else:
            feedback_parts.append("✗ Código ausente")

        # Critério 2: Thought (0.2)
        if "thought" in proposal and len(proposal["thought"]) > 10:
            score += 0.2
            feedback_parts.append("✓ Thought")
        else:
            feedback_parts.append("✗ Thought fraco")

        # Critério 3: Erro handling (0.2)
        code = proposal.get("code", "")
        if "try" in code or "except" in code or "if " in code:
            score += 0.2
            feedback_parts.append("✓ Error handling")
        else:
            score += 0.05
            feedback_parts.append("~ S/ error handling")

        # Critério 4: Output (0.15)
        if "print" in code or "return" in code:
            score += 0.15
            feedback_parts.append("✓ Output")
        else:
            feedback_parts.append("✗ S/ output")

        # Critério 5: Estratégia (0.15)
        if "strategy" in proposal:
            score += 0.15
            feedback_parts.append("✓ Strategy")
        else:
            score += 0.05
            feedback_parts.append("~ S/ strategy")

        return {
            "score": round(score, 2),
            "feedback": " | ".join(feedback_parts),
            "approved": score >= 0.5,
            "proposal_id": proposal.get("id", "unknown"),
        }
