"""
KOSMOS Agent — Motor Cognitivo Principal
=========================================
KosmosEngine: loop cognitivo com Tree of Thoughts, Mixture of Agents,
execução isolada em microVMs Firecracker, Reflexion, e memória FAISS.

Fluxo:
    USUÁRIO → Tree of Thoughts → Mixture of Agents → Tool Router
    → MicroVM Sandbox (Firecracker) → Reflexion → Memória Episódica
    → Replanejamento (se necessário) → Loop

Uso:
    python main.py
    python main.py --task "calcular fibonacci de 10" --max-iter 8
"""

import sys
import os
import uuid
import time
import logging
import argparse
from typing import Optional

from planner_tot import ToTPlanner
from tool_router import ToolRouter
from reflexion import Reflexion
from memory import EpisodicMemory
from microvm_config import MicroVMConfig
from llm_client import DeepSeekClient, LLMConfig, set_api_key

# ─── Logging ───
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kosmos.engine")


# ─── Banner ───
BANNER = r"""
############################################################
#                                                          #
#   CNGSM CODE - AUTO-DEV                                  #
#   Autonomous Agent | Mixture of Agents | Reflexion       #
#                                                          #
############################################################
"""


def sanitize_emojis(text: str) -> str:
    """Remove ou substitui emojis apenas se o encoder falhar, mas prioriza UTF-8."""
    # Tenta manter original, remove apenas se necessário no Windows antigo
    return text

def safe_print(*args, **kwargs):
    """Print que garante UTF-8 no terminal Windows e faz flush."""
    # Configura stdout para UTF-8 se estiver no Windows
    if os.name == 'nt' and hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
            
    new_args = [str(arg) for arg in args]
    try:
        print(*new_args, **kwargs)
        sys.stdout.flush()
    except UnicodeEncodeError:
        # Fallback definitivo: remove tudo que não for ascii
        clean_args = [str(arg).encode('ascii', 'ignore').decode('ascii') for arg in new_args]
        print(*clean_args, **kwargs)
        sys.stdout.flush()

class KosmosEngine:
    """
    Motor Cognitivo KOSMOS.

    Integra:
    - ToTPlanner: planejamento Tree of Thoughts paralelo
    - ToolRouter: roteamento para MicroVM Sandbox / Jupyter
    - Reflexion: crítico multi-passo com escalação de estratégia
    - EpisodicMemory: memória vetorial FAISS

    Loop: Plan → Execute → Critique → Store → (Replan se falha)
    """

    MAX_ITERATIONS = 6

    def __init__(
        self,
        max_iterations: int = 6,
        branches: int = 4,
        sandbox_config: Optional[MicroVMConfig] = None,
        verbose: bool = True,
        api_key: Optional[str] = None,
        use_llm: bool = True,
    ):
        self.max_iterations = max_iterations
        self.verbose = verbose

        # ─── Configura LLM ───
        self._llm_client = None
        if use_llm and api_key:
            set_api_key(api_key)
            self._llm_client = DeepSeekClient(
                LLMConfig(api_key=api_key)
            )
            logger.info("DeepSeek LLM configurado")

        # Componentes
        self.planner = ToTPlanner(branches=branches)
        self.router = ToolRouter(sandbox_config=sandbox_config)
        self.critic = Reflexion()
        self.memory = EpisodicMemory()
        self.chat_history: List[Dict[str, str]] = []

        # Configura LLM nos agentes
        if self._llm_client:
            self.planner.proposer._llm = self._llm_client
            self.planner.proposer.use_llm = True
            self.planner.reviewer._llm = self._llm_client
            self.planner.reviewer.use_llm = True
        else:
            self.planner.proposer.use_llm = False
            self.planner.reviewer.use_llm = False

        # Tracking
        self.session_id = str(uuid.uuid4())[:8]
        self._start_time = None

        llm_status = 'DeepSeek' if self._llm_client else 'templates'
        logger.info(
            f"KosmosEngine inicializado "
            f"(session={self.session_id}, "
            f"max_iter={max_iterations}, "
            f"branches={branches}, "
            f"llm={llm_status})"
        )

    def run(self, task: str) -> dict:
        """
        Executa o loop cognitivo completo para uma tarefa.

        Args:
            task: descrição da tarefa em linguagem natural

        Returns:
            Resultado final da execução

        Raises:
            RuntimeError: se MAX_ITERATIONS atingido sem sucesso
        """
        self._start_time = time.time()

        # ─── 0. DETECCAO DE INTENÇÃO (Fast Path) ───
        if self._llm_client:
            intent = self._llm_client.detect_intent(task)
            if intent == "CHAT":
                if self.verbose:
                    safe_print(f"  [Chat] Resposta direta ativada...")
                
                # Importa dinamicamente para evitar circular dependecies
                from llm_client import SYSTEM_PROMPT_CHAT
                response = self._llm_client.chat(
                    user_message=task,
                    system_prompt=SYSTEM_PROMPT_CHAT,
                    history=self.chat_history
                )
                
                # Atualiza historico
                self.chat_history.append({"role": "user", "content": task})
                self.chat_history.append({"role": "assistant", "content": response})
                
                if self.verbose:
                    safe_print(f"\n  [CNGSM CODE]: {response}\n")
                
                return {
                    "status": "success",
                    "result": response,
                    "mode": "CHAT",
                    "iterations": 0
                }

        if self.verbose:
            try:
                safe_print(BANNER)
            except Exception:
                # Fallback para terminais que não suportam UTF-8/Box-drawing
                safe_print("="*60)
                safe_print("   CNGSM CODE - Autonomous Engine v3.0")
                safe_print("="*60)
            
            safe_print(f"  🎯 Tarefa: {task}")
            safe_print(f"  🔧 Session: {self.session_id}")
            safe_print(f"  ⚙️  Max Iterations: {self.max_iterations}")
            llm_status = '🧠 DeepSeek' if self._llm_client else '📋 Templates'
            safe_print(f"  🤖 LLM: {llm_status}")
            safe_print()

        current_task = task

        for iteration in range(self.max_iterations):
            elapsed = time.time() - self._start_time

            if self.verbose:
                safe_print(f"\n{'='*60}")
                safe_print(f"  ITERACAO {iteration}/{self.max_iterations} "
                      f"({elapsed:.1f}s)")
                safe_print(f"{'='*60}")

            # ─── 1. PLANEJAMENTO (Tree of Thoughts) ───
            if self.verbose:
                safe_print(f"\n  🌳 [ToT] Gerando árvore de pensamentos...")

            # Contexto da memória para informar o planejador
            context = self._build_context(current_task)
            plan = self.planner.generate_tree(current_task, context)

            if self.verbose:
                safe_print(f"  💡 Thought: {plan.get('thought', '')[:80]}")
                safe_print(f"  🔧 Strategy: {plan.get('strategy', 'unknown')}")
                tot_meta = plan.get("_tot_metadata", {})
                if tot_meta:
                    safe_print(f"  📊 Scores: {tot_meta.get('all_scores', [])}")

            # ─── 2. EXECUÇÃO (Tool Router → MicroVM Sandbox) ───
            if self.verbose:
                safe_print(f"\n  🚀 [Execute] Roteando para: {plan.get('tool', 'python')}")

            result = self.router.execute(plan)

            if self.verbose:
                if result.get("output"):
                    output_preview = str(result["output"])[:200]
                    safe_print(f"  📤 Output: {output_preview}")
                if result.get("error"):
                    safe_print(f"  ❌ Error: {result['error'][:200]}")

            # ─── 3. REFLEXION (Crítico) ───
            if self.verbose:
                safe_print(f"\n  🔍 [Reflexion] Avaliando resultado...")

            critique = self.critic.evaluate(plan, result, current_task)

            if self.verbose:
                status = "✅ SUCESSO" if critique.success else "❌ FALHA"
                safe_print(f"  {status} (confidence={critique.confidence:.2f})")
                safe_print(f"  📝 Feedback: {critique.feedback[:100]}")
                safe_print(f"  🎯 Strategy: {critique.strategy}")

            # ─── 4. MEMÓRIA ───
            self.memory.store(
                task=current_task,
                plan=plan,
                result=result,
                critique=critique.to_dict(),
                iteration=iteration,
            )

            # ─── 5. DECISÃO ───
            if critique.success:
                total_time = time.time() - self._start_time

                if self.verbose:
                    safe_print(f"\n{'='*60}")
                    safe_print(f"  🏆 TAREFA CONCLUÍDA!")
                    safe_print(f"  ⏱  Tempo total: {total_time:.2f}s")
                    safe_print(f"  🔄 Iterações: {iteration + 1}")
                    mem_summary = self.memory.summary()
                    safe_print(f"  📊 Success rate: "
                          f"{mem_summary['success_rate']:.0%}")
                    safe_print(f"{'='*60}\n")

                return {
                    "status": "success",
                    "result": result,
                    "iterations": iteration + 1,
                    "total_time": total_time,
                    "session_id": self.session_id,
                    "memory_summary": self.memory.summary(),
                    "reflexion_summary": self.critic.get_learning_summary(),
                }

            # ─── 6. REPLANEJAMENTO ───
            if critique.replan:
                if self.verbose:
                    safe_print(f"\n  🔄 [Replan] {critique.replan}")
                current_task = f"{task} [{critique.replan}]"

            # Pausa breve entre iterações
            time.sleep(0.5)

        # ─── MAX_ITERATIONS atingido ───
        total_time = time.time() - self._start_time

        if self.verbose:
            safe_print(f"\n{'='*60}")
            safe_print(f"  ⚠️  MAX_ITERATIONS ATINGIDO ({self.max_iterations})")
            safe_print(f"  ⏱  Tempo total: {total_time:.2f}s")
            learning = self.critic.get_learning_summary()
            safe_print(f"  📊 Erros: {learning['error_distribution']}")
            safe_print(f"{'='*60}\n")

        return {
            "status": "max_iterations",
            "result": None,
            "iterations": self.max_iterations,
            "total_time": total_time,
            "session_id": self.session_id,
            "memory_summary": self.memory.summary(),
            "reflexion_summary": self.critic.get_learning_summary(),
        }

    def _build_context(self, task: str) -> dict:
        """Constroi contexto a partir da memoria para informar o planejador."""
        context = {
            "recent_episodes": [
                ep.to_dict() for ep in self.memory.get_recent(3)
            ],
            "failures": len(self.memory.get_failures()),
            "successes": len(self.memory.get_successes()),
        }

        # Busca episodios similares
        similar = self.memory.search(task, k=2)
        if similar:
            context["similar_episodes"] = [ep.to_dict() for ep in similar]

        return context

    def shutdown(self):
        """Desliga todos os componentes."""
        self.router.shutdown()
        logger.info(f"KosmosEngine {self.session_id} encerrado")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


# ─── CLI ───

def parse_args():
    parser = argparse.ArgumentParser(
        description="KOSMOS Cognitive Engine — Firecracker MicroVM + DeepSeek LLM"
    )
    parser.add_argument(
        "--task", "-t",
        type=str,
        default="Calcular 2 + 2",
        help="Tarefa para o agente executar",
    )
    parser.add_argument(
        "--max-iter", "-m",
        type=int,
        default=6,
        help="Número máximo de iterações (default: 6)",
    )
    parser.add_argument(
        "--branches", "-b",
        type=int,
        default=4,
        help="Número de branches no Tree of Thoughts (default: 4)",
    )
    parser.add_argument(
        "--api-key", "-k",
        type=str,
        default=os.environ.get("DEEPSEEK_API_KEY", ""),
        help="DeepSeek API key (ou set DEEPSEEK_API_KEY env var)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Desabilita LLM (usa templates locais)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Modo silencioso (sem output visual)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    api_key = args.api_key if not args.no_llm else None

    # Se uma tarefa foi passada via flag, executa uma vez e sai
    if args.task:
        with KosmosEngine(
            max_iterations=args.max_iter,
            branches=args.branches,
            verbose=not args.quiet,
            api_key=api_key,
            use_llm=not args.no_llm,
        ) as engine:
            engine.run(args.task)
    else:
        # Modo Interativo (Loop CLI)
        with KosmosEngine(
            max_iterations=args.max_iter,
            branches=args.branches,
            verbose=not args.quiet,
            api_key=api_key,
            use_llm=not args.no_llm,
        ) as engine:
            try:
                safe_print(BANNER)
                safe_print("  🚀 [CNGSM CODE] Modo Interativo Ativado.")
                safe_print("  (Digite 'sair' ou 'exit' para encerrar)\n")
                
                while True:
                    task = input("\n👤 Usuário: ").strip()
                    if task.lower() in ["sair", "exit", "quit"]:
                        break
                    if not task:
                        continue
                    
                    result = engine.run(task)
                    
                    # Para CHAT, o resultado é a string. Para TECHNICAL, buscamos o output.
                    if result["status"] == "success":
                        res_text = result['result'] if isinstance(result['result'], str) else result['result'].get('output', 'Tarefa concluída')
                        safe_print(f"\n✅ Resultado: {res_text}")
                    else:
                        safe_print(f"\n⚠️  Agente não completou a tarefa")
            except KeyboardInterrupt:
                safe_print("\n  Encerrando sessão interativa...")


if __name__ == "__main__":
    main()
