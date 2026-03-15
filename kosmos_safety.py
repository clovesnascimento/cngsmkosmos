"""
kosmos_safety.py — KOSMOS Stage 5 Solution
===========================================
F11 — HumanInTheLoop (HITL):
    - Analisa risco do código antes de executar
    - Auto-aprova código seguro (I/O simples, print, cálculos)
    - Auto-rejeita código perigoso (rm, format, exec, curl|bash)
    - Solicita aprovação humana para código de risco médio

F12 — RefinedReflexion:
    - Classifica erros em 5 tipos distintos
    - Cada tipo tem estratégia de recuperação específica
    - Syntax → rewrite_code (não replanejamento)
    - Logic  → fix_logic
    - Timeout → simplify_or_chunk
    - OOM     → chunk_data
    - File    → check_path

F13 — SemanticLogger:
    - Logs estruturados com campos obrigatórios
    - Eventos tipados: attempt, skill_route, loop_detected, hitl, error
    - Serialização JSON para análise externa
    - Estatísticas de sessão em tempo real
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("kosmos.safety")


# ══════════════════════════════════════════════════════════════════
# F11 — HUMAN IN THE LOOP
# ══════════════════════════════════════════════════════════════════

# Padrões de código PERIGOSO — bloqueio automático
DANGEROUS_PATTERNS = [
    # Destruição de sistema de arquivos
    (r'rm\s+-rf\s+/', "comando rm -rf /"),
    (r"subprocess.*['\"]rm['\"].*['\"]\-rf", "subprocess rm -rf"),
    (r"['\"]rm['\"].*['\"]\-rf", "rm -rf em lista"),
    (r'shutil\.rmtree\s*\(\s*["\'][/\\]', "rmtree em path raiz"),
    (r'shutil\.rmtree\s*\(\s*["\']workspace["\']', "rmtree no workspace"),
    (r'format\s+[a-zA-Z]:', "comando format de drive"),
    (r'os\.remove\s*\(\s*__file__', "delete do próprio arquivo"),

    # Execução arbitrária
    (r'\bexec\s*\(', "uso de exec()"),
    (r'\beval\s*\(.*open\s*\(', "eval com open()"),
    (r'__import__.*os.*system', "import dinâmico de os.system"),

    # Exfiltração de dados
    (r'curl\s+.*\|\s*bash', "curl pipe bash"),
    (r'wget\s+.*\|\s*sh', "wget pipe sh"),
    (r'Invoke-WebRequest.*\|\s*iex', "PowerShell download+exec"),

    # Acesso a arquivos sensíveis
    (r'open\s*\(\s*["\'][/\\]etc[/\\]passwd', "leitura de /etc/passwd"),
    (r'open\s*\(\s*["\'][/\\]etc[/\\]shadow', "leitura de /etc/shadow"),
    (r'open\s*\(\s*["\']C:[/\\]Windows', "acesso a C:\\Windows"),

    # Escalada de privilégios
    (r'subprocess.*sudo', "subprocess com sudo"),
    (r'os\.system.*sudo', "os.system com sudo"),
    (r'chmod\s+777', "chmod 777"),
]

# Padrões de código de RISCO MÉDIO — solicitar aprovação humana
MEDIUM_RISK_PATTERNS = [
    (r'subprocess\.run|subprocess\.Popen|os\.system', "execução de subprocesso"),
    (r'os\.remove\b|os\.unlink\b', "deleção de arquivo"),
    (r'shutil\.rmtree\b', "deleção de diretório"),
    (r'requests\.(?:post|put|delete|patch)', "requisição HTTP mutante"),
    (r'socket\.connect', "conexão de socket"),
    (r'import\s+paramiko|import\s+fabric', "SSH"),
    (r'open.*["\'][wax]["\'].*outside_workspace', "escrita fora do workspace"),
]

# Padrões claramente SEGUROS — aprovação automática
SAFE_INDICATORS = [
    r'^\s*print\s*\(',
    r'^\s*import\s+(os|sys|json|math|re|time|datetime|pathlib|collections)',
    r'^\s*#',
    r'^\s*$',
]


class HumanInTheLoop:
    """
    Interceptor de segurança para código gerado pelo LLM.

    Em produção, código de risco médio pode ser configurado para:
    - auto_approve_safe=True:      aprova código seguro sem perguntar
    - auto_reject_dangerous=True:  rejeita código perigoso sem perguntar
    - Risco médio: solicita input humano (em modo interativo)
                  ou rejeita (em modo não-interativo)
    """

    def __init__(
        self,
        auto_approve_safe: bool = True,
        auto_reject_dangerous: bool = True,
        interactive: bool = False,
    ):
        self.auto_approve_safe      = auto_approve_safe
        self.auto_reject_dangerous  = auto_reject_dangerous
        self.interactive            = interactive

    def review(self, code: str, task: str = "") -> Dict[str, Any]:
        """
        Analisa o código e retorna decisão de aprovação.

        Returns:
            {
                "approved": bool,
                "risk_level": "safe" | "low" | "medium" | "dangerous",
                "reason": str,
                "patterns_found": list,
            }
        """
        risk_level, patterns = self._assess_risk(code)

        if risk_level == "dangerous":
            if self.auto_reject_dangerous:
                reason = f"Código bloqueado automaticamente: {', '.join(patterns)}"
                logger.warning(f"HITL: REJEITADO [{risk_level}] — {reason}")
                return {
                    "approved": False,
                    "risk_level": risk_level,
                    "reason": reason,
                    "patterns_found": patterns,
                }

        if risk_level in ("safe", "low"):
            if self.auto_approve_safe:
                return {
                    "approved": True,
                    "risk_level": risk_level,
                    "reason": "Código aprovado automaticamente (baixo risco)",
                    "patterns_found": [],
                }

        if risk_level == "medium":
            if not self.interactive:
                # Modo não-interativo: rejeita código de risco médio
                reason = f"Aprovação humana necessária: {', '.join(patterns)}"
                logger.warning(f"HITL: PENDENTE [{risk_level}] — {reason}")
                return {
                    "approved": False,
                    "risk_level": risk_level,
                    "reason": reason,
                    "patterns_found": patterns,
                    "requires_human": True,
                }
            else:
                # Modo interativo: solicita input
                return self._request_human_approval(code, task, patterns)

        return {
            "approved": True,
            "risk_level": risk_level,
            "reason": "Aprovado",
            "patterns_found": patterns,
        }

    def _assess_risk(self, code: str) -> tuple:
        """Avalia o risco do código. Retorna (risk_level, patterns_found)."""

        # Verifica padrões PERIGOSOS primeiro
        found_dangerous = []
        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                found_dangerous.append(description)

        if found_dangerous:
            return "dangerous", found_dangerous

        # Verifica padrões de RISCO MÉDIO
        found_medium = []
        for pattern, description in MEDIUM_RISK_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                found_medium.append(description)

        if found_medium:
            return "medium", found_medium

        # Código seguro
        return "safe", []

    def _request_human_approval(
        self, code: str, task: str, patterns: List[str]
    ) -> Dict[str, Any]:
        """Solicita aprovação humana via input interativo."""
        print(f"\n{'='*55}")
        print("  ⚠  KOSMOS HITL — APROVAÇÃO NECESSÁRIA")
        print(f"{'='*55}")
        print(f"  Tarefa: {task[:60]}")
        print(f"  Padrões detectados: {', '.join(patterns)}")
        print(f"\n  Código:\n  {'─'*50}")
        for line in code.split("\n")[:20]:
            print(f"  {line}")
        if code.count("\n") > 20:
            print(f"  ... ({code.count(chr(10)) - 20} linhas omitidas)")
        print(f"  {'─'*50}\n")

        try:
            answer = input("  Aprovar execução? [s/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        approved = answer in ("s", "sim", "y", "yes")
        return {
            "approved": approved,
            "risk_level": "medium",
            "reason": "Aprovado pelo usuário" if approved else "Rejeitado pelo usuário",
            "patterns_found": patterns,
        }


# ══════════════════════════════════════════════════════════════════
# F12 — REFINED REFLEXION ERROR CLASSIFIER
# ══════════════════════════════════════════════════════════════════

ERROR_CLASSIFICATIONS = [
    # (padrão_no_erro, exit_code_opcional, tipo, estratégia, descrição)
    (r"SyntaxError|IndentationError|TabError|unexpected EOF",
     None, "syntax", "rewrite_code",
     "Erro de sintaxe Python — reescrever o código"),

    (r"NameError|AttributeError|TypeError|ValueError|KeyError|IndexError",
     None, "logic", "fix_logic",
     "Erro lógico — corrigir a lógica, não reescrever tudo"),

    (r"\[TIMEOUT\]|timeout.*após|TimeoutExpired",
     None, "timeout", "simplify_or_chunk",
     "Timeout — simplificar ou dividir em partes menores"),

    (r"\[OOM\]|MemoryError|Cannot allocate|exit code 137",
     137, "oom", "chunk_data",
     "Out of Memory — processar dados em chunks menores"),

    (r"FileNotFoundError|No such file|ENOENT|cannot find",
     None, "file_not_found", "check_path",
     "Arquivo não encontrado — verificar path"),

    (r"PermissionError|Permission denied|EACCES|Access denied",
     None, "permission", "check_permissions",
     "Sem permissão — verificar permissões do arquivo"),

    (r"ConnectionError|requests\.exceptions|urllib.*error|socket\.error",
     None, "network", "check_network",
     "Erro de rede — verificar conectividade"),

    (r"ImportError|ModuleNotFoundError|No module named",
     None, "import_error", "install_dependency",
     "Módulo não encontrado — instalar dependência"),
]

FALLBACK_CLASSIFICATION = ("logical_or_unknown", "retry",
                           "Erro desconhecido — tentar novamente")


class RefinedReflexion:
    """
    Classificador de erros refinado para o Reflexion.
    Distingue tipos de erro e sugere estratégias específicas.
    """

    def classify(
        self,
        error: str,
        exit_code: int = -1,
        output: str = "",
    ) -> Dict[str, Any]:
        """
        Classifica o erro e retorna tipo + estratégia de recuperação.

        Returns:
            {
                "error_type": str,
                "strategy": str,
                "description": str,
                "confidence": float,
            }
        """
        if not error:
            # Sem erro mas saiu com código não-zero
            if exit_code == 137:
                return {
                    "error_type": "oom",
                    "strategy": "chunk_data",
                    "description": "OOM detectado via exit code 137",
                    "confidence": 0.95,
                }
            if exit_code != 0:
                return {
                    "error_type": "logical_or_unknown",
                    "strategy": "retry",
                    "description": "Saída não-zero sem mensagem de erro",
                    "confidence": 0.3,
                }

        error_text = (error or "").lower()

        for pattern, ec, err_type, strategy, desc in ERROR_CLASSIFICATIONS:
            # Match por exit code específico
            if ec is not None and exit_code == ec:
                return {
                    "error_type": err_type,
                    "strategy": strategy,
                    "description": desc,
                    "confidence": 0.95,
                }
            # Match por padrão no texto do erro
            if re.search(pattern, error or "", re.IGNORECASE):
                return {
                    "error_type": err_type,
                    "strategy": strategy,
                    "description": desc,
                    "confidence": 0.9,
                }

        # Fallback
        err_type, strategy, desc = FALLBACK_CLASSIFICATION
        return {
            "error_type": err_type,
            "strategy": strategy,
            "description": desc,
            "confidence": 0.2,
        }

    def get_replan_instruction(self, error_type: str, error: str) -> str:
        """Gera instrução de replanejamento específica para o tipo de erro."""
        instructions = {
            "syntax": (
                "ERRO DE SINTAXE PYTHON detectado. "
                "Reescreva o código do zero com sintaxe válida. "
                "NUNCA use triple-quotes para HTML. Use f.write() linha a linha."
            ),
            "logic": (
                "ERRO LÓGICO detectado. Analise o traceback e corrija apenas "
                "a parte que falhou. Não reescreva código que funcionou."
            ),
            "timeout": (
                "TIMEOUT detectado. Simplifique a tarefa ou divida em partes menores. "
                "Se for HTML grande, use write_file no JSON em vez de Python."
            ),
            "oom": (
                "OUT OF MEMORY detectado. Processe os dados em chunks de 50MB. "
                "Libere memória (del variável) entre os chunks."
            ),
            "file_not_found": (
                "ARQUIVO NÃO ENCONTRADO. Verifique o path. "
                "O Docker está em /workspace — não use prefixo workspace/. "
                "Liste os arquivos com os.listdir('.') antes de abrir."
            ),
            "import_error": (
                "MÓDULO NÃO ENCONTRADO. Use apenas stdlib Python ou "
                "os pacotes já instalados no container python:3.11-slim."
            ),
        }
        return instructions.get(
            error_type,
            f"Erro de {error_type}. Analise o traceback e corrija: {error[:100]}"
        )


# ══════════════════════════════════════════════════════════════════
# F13 — SEMANTIC LOGGER
# ══════════════════════════════════════════════════════════════════

class SemanticLogger:
    """
    Logger estruturado com eventos tipados e estatísticas de sessão.
    Todos os eventos têm campos obrigatórios: timestamp, event_type, session_id.
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._events: List[Dict[str, Any]] = []

    def _emit(self, event_type: str, **kwargs) -> Dict[str, Any]:
        """Emite um evento estruturado."""
        event = {
            "timestamp":  datetime.now().isoformat(),
            "event_type": event_type,
            "session_id": self.session_id,
            **kwargs,
        }
        self._events.append(event)
        logger.debug(f"SemanticLogger: {event_type} | {json.dumps(kwargs)[:100]}")
        return event

    def log_attempt(
        self,
        task: str,
        attempt: int,
        strategy: str,
        success: bool,
        error_type: Optional[str] = None,
        duration: float = 0.0,
    ):
        self._emit(
            "attempt",
            task=task[:100],
            attempt=attempt,
            strategy=strategy,
            success=success,
            error_type=error_type,
            duration_seconds=round(duration, 2),
        )

    def log_skill_route(
        self,
        task: str,
        skill: str,
        score: float,
        method: str = "keyword",
    ):
        self._emit(
            "skill_route",
            task=task[:100],
            skill=skill,
            score=round(score, 3),
            method=method,
        )

    def log_loop_detected(
        self,
        task: str,
        strategy: str,
        count: int,
        alternative: str,
    ):
        self._emit(
            "loop_detected",
            task=task[:100],
            strategy=strategy,
            repeat_count=count,
            alternative_suggested=alternative,
        )

    def log_hitl(
        self,
        task: str,
        risk_level: str,
        approved: bool,
        reason: str,
    ):
        self._emit(
            "hitl",
            task=task[:100],
            risk_level=risk_level,
            approved=approved,
            reason=reason[:200],
        )

    def log_error(
        self,
        task: str,
        error_type: str,
        error_msg: str,
        strategy: str,
    ):
        self._emit(
            "error",
            task=task[:100],
            error_type=error_type,
            error_msg=error_msg[:200],
            recovery_strategy=strategy,
        )

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def get_stats(self) -> Dict[str, Any]:
        attempts    = [e for e in self._events if e["event_type"] == "attempt"]
        loops       = [e for e in self._events if e["event_type"] == "loop_detected"]
        hitl_events = [e for e in self._events if e["event_type"] == "hitl"]

        total_attempts  = len(attempts)
        successful      = sum(1 for a in attempts if a.get("success"))
        success_rate    = successful / total_attempts if total_attempts > 0 else 0.0

        error_types = {}
        for a in attempts:
            et = a.get("error_type")
            if et:
                error_types[et] = error_types.get(et, 0) + 1

        return {
            "total_attempts":   total_attempts,
            "successful":       successful,
            "success_rate":     round(success_rate, 2),
            "loops_detected":   len(loops),
            "hitl_reviews":     len(hitl_events),
            "hitl_rejected":    sum(1 for h in hitl_events if not h.get("approved")),
            "error_breakdown":  error_types,
            "total_events":     len(self._events),
        }

    def to_json(self) -> str:
        return json.dumps(self._events, ensure_ascii=False, indent=2)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        logger.info(f"SemanticLogger: {len(self._events)} eventos salvos em {path}")


if __name__ == "__main__":
    print("kosmos_safety.py — Demo\n")

    # HITL
    print("HumanInTheLoop:")
    hitl = HumanInTheLoop(auto_approve_safe=True, auto_reject_dangerous=True)
    safe   = hitl.review("print('hello')", "teste")
    danger = hitl.review("import os; os.system('rm -rf /')", "teste")
    print(f"  Código seguro:   approved={safe['approved']} risk={safe['risk_level']}")
    print(f"  Código perigoso: approved={danger['approved']} risk={danger['risk_level']}")

    # RefinedReflexion
    print("\nRefinedReflexion:")
    ref = RefinedReflexion()
    errors = [
        ("SyntaxError: invalid syntax", 1),
        ("NameError: name 'x' is not defined", 1),
        ("[TIMEOUT] após 120s", -1),
        ("", 137),
        ("FileNotFoundError: 'data.csv'", 1),
    ]
    for err, ec in errors:
        r = ref.classify(err, ec)
        print(f"  [{r['error_type']:20}] → {r['strategy']:20} | {err[:40]}")

    # SemanticLogger
    print("\nSemanticLogger:")
    slog = SemanticLogger(session_id="demo")
    slog.log_attempt("criar landing page", 1, "llm_generated", False, "syntax", 45.2)
    slog.log_attempt("criar landing page", 2, "write_file", True, None, 12.1)
    slog.log_loop_detected("criar landing page", "llm_generated", 3, "write_file")
    stats = slog.get_stats()
    print(f"  {len(slog.get_events())} eventos | stats={stats}")

    print("\n✓ Demo concluído")
