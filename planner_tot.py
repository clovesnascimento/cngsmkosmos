"""
KOSMOS Agent — Tree of Thoughts Planner (Paralelo)
===================================================
Gera múltiplas propostas em paralelo via ThreadPoolExecutor,
revisa cada uma, e seleciona a melhor via pontuação.
"""

import logging
import concurrent.futures
from typing import Dict, Any, List, Optional

from agents import ProposerAgent, ReviewerAgent

logger = logging.getLogger("kosmos.planner")


class ToTPlanner:
    """
    Tree of Thoughts Planner com exploração paralela.

    Gera N propostas simultaneamente (branches do ToT),
    avalia cada uma com o ReviewerAgent, e retorna a melhor.

    Fluxo:
        1. Spawn N ProposerAgents em threads paralelas
        2. Cada um gera uma proposta com estratégia diferente
        3. ReviewerAgent pontua cada proposta
        4. Proposta com maior score é selecionada

    Uso:
        planner = ToTPlanner(branches=4)
        best_plan = planner.generate_tree("calcular fibonacci")
    """

    def __init__(self, branches: int = 4, max_workers: int = 4):
        self.branches = branches
        self.max_workers = max_workers
        self.proposer = ProposerAgent()
        self.reviewer = ReviewerAgent()
        self._generation_count = 0

    def generate_tree(
        self,
        task: str,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Gera árvore de pensamentos e retorna o melhor plano.

        Args:
            task: descrição da tarefa
            context: contexto adicional (memória, feedback anterior)

        Returns:
            O melhor plano segundo o ReviewerAgent
        """
        self._generation_count += 1

        logger.info(
            f"ToT Generation #{self._generation_count}: "
            f"task='{task}', branches={self.branches}"
        )

        # ─── Gera propostas em paralelo ───
        proposals = self._parallel_propose(task, context)

        if not proposals:
            logger.error("Nenhuma proposta gerada")
            return self._fallback_plan(task)

        # ─── Revisa e pontua ───
        self.reviewer.set_task(task)
        scored = []
        for proposal in proposals:
            review = self.reviewer.review(proposal)
            scored.append({
                "proposal": proposal,
                "review": review,
                "score": review["score"],
            })

        # ─── Ordena por score (maior primeiro) ───
        scored.sort(key=lambda x: x["score"], reverse=True)

        best = scored[0]
        logger.info(
            f"ToT: Melhor proposta #{best['proposal'].get('id')} "
            f"(score={best['score']:.2f}, "
            f"strategy={best['proposal'].get('strategy')})"
        )

        # Adiciona metadata do ToT ao plano vencedor
        best_plan = best["proposal"]
        best_plan["_tot_metadata"] = {
            "generation": self._generation_count,
            "total_branches": len(proposals),
            "winning_score": best["score"],
            "all_scores": [s["score"] for s in scored],
            "runner_up_score": scored[1]["score"] if len(scored) > 1 else None,
        }

        return best_plan

    def _parallel_propose(self, task: str, context: dict) -> list:
        """Gera propostas. Paralelo se branches > 1, sequencial se 1."""
        if self.branches <= 1:
            return [self.proposer.propose(task, context)]
            
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.branches) as executor:
            for i in range(self.branches):
                futures.append(executor.submit(self.proposer.propose, task, context))
        
        proposals = []
        for future in concurrent.futures.as_completed(futures):
                try:
                    proposal = future.result(timeout=10)
                    proposals.append(proposal)
                except Exception as e:
                    logger.warning(f"Proposta falhou: {e}")
        return proposals

    def _fallback_plan(self, task: str) -> Dict[str, Any]:
        """Plano de fallback quando o ToT falha."""
        return {
            "id": -1,
            "thought": f"Fallback: executar tarefa diretamente: {task}",
            "tool": "python",
            "code": f"result = '{task}'\nprint(result)",
            "strategy": "fallback",
        }

    def generate_tree_iterative(
        self,
        task: str,
        depth: int = 2,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        ToT iterativo: gera árvore em múltiplas profundidades.
        Cada nível refina o melhor plano do nível anterior.

        Args:
            task: descrição da tarefa
            depth: profundidade da árvore (nível de refinamento)
            context: contexto adicional

        Returns:
            O plano mais refinado
        """
        current_task = task
        best_plan = None

        for level in range(depth):
            logger.info(f"ToT Nível {level}/{depth}")

            plan = self.generate_tree(current_task, context)

            if best_plan is not None:
                # Refina baseado no plano anterior
                current_task = (
                    f"Refinar: {task}. "
                    f"Plano anterior: {plan.get('thought', '')}. "
                    f"Estratégia: {plan.get('strategy', '')}"
                )

            best_plan = plan

        return best_plan
