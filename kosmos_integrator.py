"""
kosmos_integrator.py — KOSMOS Agent v2.5
=========================================
Integra os 5 módulos da Pirâmide de Robustez ao KosmosEngine.

Pontos de integração no main.py:

  PONTO 1 — __init__: inicializa os 5 módulos como atributos do engine
  PONTO 2 — run() início: injeta lições da memória no current_task
  PONTO 3 — antes de execute(): HITL verifica risco do código
  PONTO 4 — antes de execute(): LoopDetector verifica loop
  PONTO 5 — após critique: armazena episódio na memória persistente
             + log semântico

Uso:
    cd D:\\FIRECRACKER\\kosmos_agent
    python kosmos_integrator.py
    python kosmos_integrator.py --dry-run
    python kosmos_integrator.py --revert
    python kosmos_integrator.py --status
"""

import sys
import shutil
import argparse
from pathlib import Path

TARGET = "main.py"
MARKER = "# [KOSMOS-v2.5] Integração Pirâmide de Robustez"


# ══════════════════════════════════════════════════════════════════
# PONTO 1 — __init__: inicialização dos módulos
# ══════════════════════════════════════════════════════════════════

P1_OLD = "        self.session_id = str(uuid.uuid4())[:8]"

P1_NEW = """        self.memory = EpisodicMemory()

        # [KOSMOS-v2.5] Integração Pirâmide de Robustez
        try:
            from kosmos_infra     import KosmosExecutor
            from kosmos_memory    import KosmosMemoryAdapter
            from kosmos_cognitive import SemanticSkillRouter, LoopDetector, PersistentSkillForge
            from kosmos_safety    import HumanInTheLoop, RefinedReflexion, SemanticLogger
            from kosmos_parser    import RobustParser, PromptCompressor

            self._v25_executor    = KosmosExecutor(session_id=self.session_id)
            self._v25_memory      = KosmosMemoryAdapter(db_path="kosmos_memory.db")
            self._v25_sem_router  = SemanticSkillRouter()
            self._v25_loop        = LoopDetector(max_repeats=2)
            self._v25_skill_forge = PersistentSkillForge("skills_registry.json")
            self._v25_hitl        = HumanInTheLoop(
                                        auto_approve_safe=True,
                                        auto_reject_dangerous=True,
                                        interactive=False,
                                    )
            self._v25_reflexion   = RefinedReflexion()
            self._v25_logger      = SemanticLogger(session_id=self.session_id)
            self._v25_parser      = RobustParser()
            self._v25_compressor  = PromptCompressor(max_tokens=3000)
            self._v25_active      = True
            import logging as _lg
            _lg.getLogger("kosmos.engine").info(
                "Pirâmide de Robustez v2.5 ativa: "
                "infra+memory+cognitive+safety+parser"
            )
        except ImportError as _e:
            self._v25_active = False
            import logging as _lg
            _lg.getLogger("kosmos.engine").warning(
                f"Módulos v2.5 não encontrados ({_e}) — modo v2.3 compatível"
            )"""


# ══════════════════════════════════════════════════════════════════
# PONTO 2 — início do loop: injeção de lições da memória
# ══════════════════════════════════════════════════════════════════

P2_OLD = "        current_task = task\n\n        for iteration in range(self.max_iterations):"

P2_NEW = """        current_task = task

        # [KOSMOS-v2.5] Injeção proativa de lições da memória persistente
        if getattr(self, '_v25_active', False):
            _lesson_injection = self._v25_memory.get_prompt_injection(task, max_lessons=3)
            if _lesson_injection and self.verbose:
                safe_print(f"  📚 [Memória] Lições relevantes encontradas")
            # Reset loop detector para nova tarefa
            self._v25_loop.reset(task)

        for iteration in range(self.max_iterations):"""


# ══════════════════════════════════════════════════════════════════
# PONTO 3 — antes de execute(): HITL + LoopDetector
# ══════════════════════════════════════════════════════════════════

P3_OLD = (
    "            # \u2500\u2500\u2500 2. EXECU\u00c7\u00c3O (Tool Router \u2192 MicroVM Sandbox) \u2500\u2500\u2500\n"
    "            if self.verbose:\n"
    "                safe_print(f\"\\n  \U0001f680 [Execute] Roteando para: {plan.get('tool', 'python')}\")\n"
    "\n"
    "            result = self.router.execute(plan)"
)

P3_NEW = """            # ─── 2. EXECUÇÃO (Tool Router → MicroVM Sandbox) ───
            if self.verbose:
                safe_print(f"  🚀 [Execute] Roteando para: {plan.get('tool', 'python')}")

            # [KOSMOS-v2.5] LoopDetector — detecta loop antes de executar
            if getattr(self, '_v25_active', False):
                _strategy = plan.get('strategy', 'llm_generated')
                if self._v25_loop.is_loop(task, _strategy):
                    _alt = self._v25_loop.suggest_alternative(task, _strategy)
                    if self.verbose:
                        safe_print(f"  🔄 [LoopDetector] Loop detectado! Alternativa: {_alt}")
                    current_task = f"{task} [FORÇAR ESTRATÉGIA: {_alt}]"
                    self._v25_logger.log_loop_detected(
                        task=task, strategy=_strategy,
                        count=3, alternative=_alt
                    )

            # [KOSMOS-v2.5] HITL — verifica risco antes de executar Python
            _hitl_approved = True
            if getattr(self, '_v25_active', False) and plan.get('tool') == 'python':
                _code = plan.get('code', '')
                if _code:
                    _hitl_result = self._v25_hitl.review(_code, task=task)
                    _hitl_approved = _hitl_result['approved']
                    if not _hitl_approved:
                        if self.verbose:
                            safe_print(f"  🛡️  [HITL] Bloqueado: {_hitl_result['reason'][:80]}")
                        self._v25_logger.log_hitl(
                            task=task,
                            risk_level=_hitl_result['risk_level'],
                            approved=False,
                            reason=_hitl_result['reason'],
                        )
                        result = {
                            "output": None,
                            "error": f"[HITL] {_hitl_result['reason']}",
                            "exit_code": -1,
                        }

            if _hitl_approved:
                result = self.router.execute(plan)"""


# ══════════════════════════════════════════════════════════════════
# PONTO 4 — após critique: log semântico + memória persistente
# ══════════════════════════════════════════════════════════════════

P4_OLD = """            # ─── 4. MEMÓRIA ───
            self.memory.store(
                task=current_task,
                plan=plan,
                result=result,
                critique=critique.to_dict(),
                iteration=iteration,
            )"""

P4_NEW = """            # ─── 4. MEMÓRIA ───
            self.memory.store(
                task=current_task,
                plan=plan,
                result=result,
                critique=critique.to_dict(),
                iteration=iteration,
            )

            # [KOSMOS-v2.5] Memória persistente + log semântico
            if getattr(self, '_v25_active', False):
                _error_msg = result.get('error') or ''
                _exit_code = result.get('exit_code', -1)

                # Classifica erro com RefinedReflexion
                if not critique.success and _error_msg:
                    _err_class = self._v25_reflexion.classify(
                        error=_error_msg, exit_code=_exit_code
                    )
                    _err_type  = _err_class['error_type']
                    _err_strat = _err_class['strategy']
                else:
                    _err_type  = None
                    _err_strat = None

                # Armazena na memória persistente
                self._v25_memory.store(
                    task=task,
                    success=critique.success,
                    error=_error_msg or None,
                    strategy=plan.get('strategy'),
                )

                # Log semântico
                self._v25_logger.log_attempt(
                    task=task,
                    attempt=iteration,
                    strategy=plan.get('strategy', 'unknown'),
                    success=critique.success,
                    error_type=_err_type,
                    duration=time.time() - self._start_time,
                )

                # Rota semântica para próxima iteração se falhou
                if not critique.success and _err_type:
                    _replan = self._v25_reflexion.get_replan_instruction(
                        _err_type, _error_msg
                    )
                    if self.verbose:
                        safe_print(f"  🧠 [v2.5] Erro classificado: {_err_type} → {_err_strat}")
                    # Sobrescreve o replan do Reflexion com um mais específico
                    if critique.replan and _err_type not in ('logical_or_unknown',):
                        critique.replan = _replan"""


def find_line(lines, text, start=0):
    for i in range(start, len(lines)):
        if text in lines[i]:
            return i
    return -1


def apply(dry_run=False):
    path = Path(TARGET)
    if not path.exists():
        print(f"ERRO: {TARGET} não encontrado.")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")

    if MARKER in content:
        print(f"Integração já aplicada. Use --revert para desfazer.")
        return

    patches = [
        ("PONTO 1 — __init__", P1_OLD, P1_NEW),
        ("PONTO 2 — injeção memória", P2_OLD, P2_NEW),
        ("PONTO 3 — HITL + LoopDetector", P3_OLD, P3_NEW),
        ("PONTO 4 — log + memória persistente", P4_OLD, P4_NEW),
    ]

    if dry_run:
        print("DRY RUN — verificando pontos de integração:")
        all_found = True
        for name, old, _ in patches:
            found = old in content
            icon = "✓" if found else "✗"
            print(f"  {icon} {name}")
            if not found:
                all_found = False
        if all_found:
            print("\n  ✅ Todos os pontos encontrados — integração pode ser aplicada")
        else:
            print("\n  ❌ Alguns pontos não encontrados — verificar versão do main.py")
        return

    # Verifica todos antes de aplicar
    missing = []
    for name, old, _ in patches:
        if old not in content:
            missing.append(name)

    if missing:
        print(f"ERRO: Pontos não encontrados: {missing}")
        print("Verifique se o main.py é a versão correta.")
        sys.exit(1)

    # Backup
    backup = TARGET + ".bak_v25"
    shutil.copy2(TARGET, backup)
    print(f"Backup: {backup}")

    # Aplica patches em ordem
    for name, old, new in patches:
        content = content.replace(old, new, 1)
        print(f"  ✓ {name}")

    path.write_text(content, encoding="utf-8")
    print(f"\nOK: {TARGET} integrado — KOSMOS v2.5 ativo")


def revert():
    backup = Path(TARGET + ".bak_v25")
    if not backup.exists():
        print("ERRO: backup não encontrado.")
        sys.exit(1)
    shutil.copy2(backup, TARGET)
    print(f"OK: {TARGET} revertido para v2.3")


def status():
    path = Path(TARGET)
    if not path.exists():
        print(f"ERRO: {TARGET} não encontrado.")
        return

    content = path.read_text(encoding="utf-8")
    integrated = MARKER in content

    print(f"\nStatus da integração v2.5:")
    print(f"  main.py:           {'integrado' if integrated else 'não integrado'}")

    modules = [
        "kosmos_infra.py",
        "kosmos_memory.py",
        "kosmos_parser.py",
        "kosmos_cognitive.py",
        "kosmos_safety.py",
    ]
    for mod in modules:
        exists = Path(mod).exists()
        print(f"  {mod}: {'✓' if exists else '✗ FALTANDO'}")

    if integrated and all(Path(m).exists() for m in modules):
        print("\n  ✅ KOSMOS v2.5 totalmente integrado e pronto")
    elif not integrated:
        print("\n  ⚠  Execute: python kosmos_integrator.py")
    else:
        print("\n  ⚠  Módulos faltando — copie os arquivos ausentes")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Integra a Pirâmide de Robustez ao KosmosEngine"
    )
    p.add_argument("--dry-run", action="store_true", help="Verifica sem aplicar")
    p.add_argument("--revert",  action="store_true", help="Desfaz a integração")
    p.add_argument("--status",  action="store_true", help="Mostra status atual")
    args = p.parse_args()

    if args.revert:
        revert()
    elif args.status:
        status()
    else:
        apply(dry_run=args.dry_run)
