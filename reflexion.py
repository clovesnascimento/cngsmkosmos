"""
KOSMOS Agent — Reflexion (Crítico Interno Multi-Passo)
=====================================================
Avalia resultados de execução, detecta padrões de falha,
gera feedback detalhado e sugere estratégias de replanejamento.
Mantém histórico para evitar loops em tentativas repetidas.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("kosmos.reflexion")


@dataclass
class CritiqueResult:
    """Resultado de uma avaliação do Reflexion."""
    success: bool
    feedback: str
    confidence: float  # 0.0 → 1.0
    replan: Optional[str] = None
    strategy: str = "default"
    attempt: int = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "feedback": self.feedback,
            "confidence": self.confidence,
            "replan": self.replan,
            "strategy": self.strategy,
            "attempt": self.attempt,
        }


class Reflexion:
    """
    Crítico Reflexion multi-passo.

    Avalia os resultados da execução e usa o histórico para:
    - Detectar falhas recorrentes (loop detection)
    - Escalar estratégia quando simples não funciona
    - Gerar feedback acionável para o planejador

    Estratégias (em ordem de escalação):
    1. retry      — tenta novamente com o mesmo plano
    2. refine     — ajusta o plano baseado no erro
    3. decompose  — quebra a tarefa em subtarefas
    4. pivot      — muda a abordagem completamente
    5. abort      — desiste (MAX attempts)

    Uso:
        critic = Reflexion()
        critique = critic.evaluate(plan, result)
        if not critique.success:
            next_task = critique.replan
    """

    STRATEGIES = ["retry", "refine", "decompose", "pivot", "abort"]
    MAX_RETRIES_PER_STRATEGY = 2

    def __init__(self):
        self.history: List[CritiqueResult] = []
        self._error_counts: Dict[str, int] = {}

    @property
    def attempt_count(self) -> int:
        return len(self.history)

    @property
    def current_strategy_index(self) -> int:
        """Determina o índice da estratégia baseado no número de falhas."""
        consecutive_failures = 0
        for critique in reversed(self.history):
            if critique.success:
                break
            consecutive_failures += 1

        idx = consecutive_failures // self.MAX_RETRIES_PER_STRATEGY
        return min(idx, len(self.STRATEGIES) - 1)

    @property
    def current_strategy(self) -> str:
        return self.STRATEGIES[self.current_strategy_index]

    def evaluate(self, plan: Dict[str, Any], result: Dict[str, Any], task: str = "") -> CritiqueResult:
        """
        Avalia um plano + resultado de execução.

        Args:
            plan: o plano executado (thought, tool, code)
            result: resultado da execução (output, error, exit_code)
            task: a tarefa original
        """
        attempt = self.attempt_count

        # ─── Caso 1: Sucesso ───
        if self._is_success(result, task):
            critique = CritiqueResult(
                success=True,
                feedback=self._format_success_feedback(plan, result),
                confidence=self._calculate_confidence(result),
                strategy="complete",
                attempt=attempt,
            )
            self.history.append(critique)
            logger.info(f"✓ Attempt {attempt}: Sucesso (confidence={critique.confidence:.2f})")
            return critique

        # ─── Caso 2: Falha ───
        error = result.get("error") or "Erro desconhecido"
        error_type = self._classify_error(str(error))
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

        strategy = self.current_strategy
        
        # Escalação Imediata para erros críticos de dev
        if error_type in ["syntax", "import_missing", "file_not_found", "undefined_name"]:
            strategy = "refine"

        replan = self._generate_replan(strategy, plan, error, error_type)

        critique = CritiqueResult(
            success=False,
            feedback=self._format_failure_feedback(error, error_type, strategy),
            confidence=0.0,
            replan=replan,
            strategy=strategy,
            attempt=attempt,
        )

        self.history.append(critique)

        logger.warning(
            f"✗ Attempt {attempt}: Falha "
            f"(type={error_type}, strategy={strategy})"
        )

        return critique

    def _is_success(self, result: Dict[str, Any], task: str = "") -> bool:
        """Determina se o resultado é um sucesso real."""
        if result.get("error"):
            return False
        if result.get("exit_code", 0) != 0:
            return False
            
        output = str(result.get("output", "")).strip()
        task_lower = task.lower().strip()
        output_lower = output.lower().strip()
        
        # ─── Falhas Explícitas de Fallback ───
        if "llm offline" in output_lower or "erro de parse" in output_lower:
            return False
            
        # ─── Heurística de Repetição de Tarefa ───
        # Se o output for apenas a tarefa, ou a tarefa + " - executado com sucesso", falhou
        # Ou se a tarefa estiver contida em um output curtíssimo
        is_repetition = (
            output_lower == task_lower or
            output_lower == f"tarefa: {task_lower}" or
            output_lower == f"{task_lower} — executado com sucesso" or
            (task_lower in output_lower and len(output_lower) < len(task_lower) + 30)
        )
        
        if is_repetition:
            return False
            
        # ─── Heurística de Criação ───
        # Se a tarefa pede para criar/gerar algo e o output é suspeitamente curto ( < 20 chars )
        if any(kw in task_lower for kw in ["crie", "gere", "escreva", "faça", "landing"]):
            if len(output) < 20 and result.get("exit_code") == 0:
                # Pode ter sido um print bobo de fallback
                return False
            
        return True

    def _classify_error(self, error: str) -> str:
        """Classifica o tipo de erro para informar a estratégia."""
        error_lower = error.lower()

        if "timeout" in error_lower:
            return "timeout"
        if "syntax" in error_lower:
            return "syntax"
        if "import" in error_lower or "module" in error_lower:
            return "import_missing"
        if "name" in error_lower and "not defined" in error_lower:
            return "undefined_name"
        if "type" in error_lower:
            return "type_error"
        if "index" in error_lower or "keyerror" in error_lower:
            return "index_error"
        if "file" in error_lower or "not found" in error_lower or "no such" in error_lower:
            return "file_not_found"
        if "permission" in error_lower or "access" in error_lower:
            return "permission_denied"
        if "connection" in error_lower or "socket" in error_lower:
            return "network_error"
        if "memory" in error_lower or "oom" in error_lower:
            return "resource_limit"
        return "logical_or_unknown"

    def _generate_replan(
        self,
        strategy: str,
        plan: Dict[str, Any],
        error: str,
        error_type: str,
    ) -> str:
        """Gera instrução de replanejamento baseada na estratégia."""

        if strategy == "retry":
            return f"Erro de {error_type}. Tente corrigir o código Python: {error[:100]}"

        elif strategy == "refine":
            if error_type == "syntax":
                return "Refinar código: Corrigir erros de sintaxe e identação Python."
            elif error_type == "import_missing":
                return "Refinar código: O módulo está ausente. Verifique o import ou use uma biblioteca alternativa."
            elif error_type == "file_not_found":
                return "Refinar código: O arquivo ou diretório não existe. Verifique o caminho no workspace ou use mkdir/write_file primeiro."
            elif error_type == "undefined_name":
                return "Refinar código: Variável ou função não definida. Verifique o escopo."
            elif error_type == "index_error":
                return "Refinar código: Erro de índice ou chave (List/Dict). Verifique os limites dos dados."
            else:
                return f"Refinar abordagem: Ocorreu um erro de {error_type}. Analise o traceback e simplifique."

        elif strategy == "decompose":
            return (
                f"Decompose: quebrar a tarefa em partes menores. "
                f"O erro '{error_type}' sugere que o problema é complexo demais "
                f"para uma única execução"
            )

        elif strategy == "pivot":
            return (
                f"Pivot: mudar a abordagem completamente. "
                f"Erros recorrentes ({self._error_counts}) indicam que "
                f"o caminho atual não é viável"
            )

        else:  # abort
            return "Abort: MAX_ITERATIONS atingido. Tarefa possivelmente impossível."

    def _format_success_feedback(self, plan: Dict, result: Dict) -> str:
        """Formata feedback de sucesso."""
        output = result.get("output", "")
        if output and len(output) > 200:
            output = output[:200] + "..."
        return f"Execução bem-sucedida. Output: {output}"

    def _format_failure_feedback(
        self, error: str, error_type: str, strategy: str
    ) -> str:
        """Formata feedback de falha."""
        return (
            f"Falha ({error_type}): {error[:300]}. "
            f"Estratégia: {strategy}. "
            f"Tentativas: {self.attempt_count}"
        )

    def _calculate_confidence(self, result: Dict) -> float:
        """Calcula confiança no resultado (0.0 → 1.0)."""
        confidence = 0.5

        # Output não-vazio aumenta confiança
        if result.get("output"):
            confidence += 0.2

        # Sem erros em tentativas anteriores
        if not any(not c.success for c in self.history):
            confidence += 0.2

        # Exit code 0
        if result.get("exit_code", -1) == 0:
            confidence += 0.1

        return min(confidence, 1.0)

    def get_learning_summary(self) -> Dict[str, Any]:
        """Resumo do que o crítico aprendeu nas iterações."""
        return {
            "total_attempts": self.attempt_count,
            "successes": sum(1 for c in self.history if c.success),
            "failures": sum(1 for c in self.history if not c.success),
            "error_distribution": dict(self._error_counts),
            "strategies_used": [c.strategy for c in self.history],
            "final_strategy": self.current_strategy,
        }

    def reset(self):
        """Reseta o crítico para uma nova tarefa."""
        self.history.clear()
        self._error_counts.clear()
        logger.info("Reflexion resetado")
