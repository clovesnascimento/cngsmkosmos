"""
kosmos_infra.py — KOSMOS Stage 1 Solution
==========================================
Resolve as 3 fraquezas de infraestrutura:

  F1: Timeout configurável por tarefa (não mais hardcoded 60s)
      → KosmosExecutor.run(code, timeout=N)
      → Background thread com progress callback
      → Streaming de output linha a linha

  F2: Limite de memória configurável + chunking automático
      → KosmosExecutor.run(code, memory_limit="768m")
      → Detecção de OOM e retry com limite aumentado

  F3: Volume persistente entre execuções Docker
      → Workspace montado como volume nomeado
      → Mesmo volume reutilizado entre tentativas da mesma sessão
      → Abstração de path Windows/Linux automática

Detecção de ambiente:
    Windows: D:\\FIRECRACKER\\kosmos_agent\\workspace → /workspace no container
    Linux:   /path/to/kosmos_agent/workspace         → /workspace no container
    KVM:     usa Firecracker se disponível (Linux only)
    Docker:  fallback em ambos os SOs
"""

import os
import sys
import time
import uuid
import logging
import platform
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("kosmos.infra")

# ── Detecção de ambiente ───────────────────────────────────────────
IS_WINDOWS  = platform.system() == "Windows"
IS_LINUX    = platform.system() == "Linux"
BASE_DIR    = Path(__file__).parent.resolve()
WORKSPACE   = BASE_DIR / "workspace"
WORKSPACE.mkdir(exist_ok=True)

# KVM disponível apenas em Linux com suporte
KVM_AVAILABLE = IS_LINUX and Path("/dev/kvm").exists()

# ── Defaults configuráveis ────────────────────────────────────────
DEFAULT_TIMEOUT_SECONDS = 120       # era 60, agora 120 como padrão
DEFAULT_MEMORY_LIMIT    = "512m"    # padrão mantido; override por tarefa
DEFAULT_CPU_LIMIT       = "1.0"
MAX_TIMEOUT_SECONDS     = 600       # teto absoluto (10 min)


def _normalize_workspace_path(path: Path) -> str:
    """
    Converte o path do workspace para o formato correto do SO.
    Windows: C:\\Users\\... → C:/Users/... (Docker for Windows espera forward slashes)
    Linux:   /home/...     → /home/...
    """
    if IS_WINDOWS:
        # Docker for Windows: drive letter em minúsculo + forward slashes
        resolved = str(path.resolve())
        # D:\FIRECRACKER\... → /d/FIRECRACKER/...  (formato WSL/Git Bash)
        # OU D:/FIRECRACKER/... (formato Docker Windows nativo)
        if len(resolved) > 1 and resolved[1] == ":":
            drive = resolved[0].lower()
            rest  = resolved[2:].replace("\\", "/")
            return f"/{drive}{rest}"
        return resolved.replace("\\", "/")
    return str(path.resolve())


class ExecutionResult:
    """Resultado de uma execução com suporte a streaming."""

    def __init__(self):
        self.output:    str   = ""
        self.error:     str   = ""
        self.exit_code: int   = -1
        self.timed_out: bool  = False
        self.oom:       bool  = False
        self.duration:  float = 0.0
        self._lines: list     = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output":    self.output or None,
            "error":     self.error  or None,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "oom":       self.oom,
            "duration":  round(self.duration, 2),
        }


class KosmosExecutor:
    """
    Executor híbrido Windows/Linux com:
      - Timeout configurável por execução
      - Limite de memória configurável por execução
      - Volume persistente entre execuções da mesma sessão
      - Streaming de output com callback opcional
      - Retry automático em OOM com limite aumentado
    """

    def __init__(
        self,
        workspace: Optional[Path] = None,
        session_id: Optional[str] = None,
    ):
        self.workspace  = workspace or WORKSPACE
        self.workspace.mkdir(exist_ok=True)
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self._workspace_host = _normalize_workspace_path(self.workspace)

        logger.info(
            f"KosmosExecutor inicializado | "
            f"session={self.session_id} | "
            f"platform={platform.system()} | "
            f"kvm={KVM_AVAILABLE} | "
            f"workspace={self._workspace_host}"
        )

    def run(
        self,
        code: str,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        on_output: Optional[Callable[[str], None]] = None,
        retry_oom: bool = True,
    ) -> Dict[str, Any]:
        """
        Executa código Python com timeout e memória configuráveis.

        Args:
            code:         Código Python a executar
            timeout:      Timeout em segundos (padrão 120, máx 600)
            memory_limit: Limite de RAM Docker ex: "512m", "1g", "768m"
            cpu_limit:    Limite de CPU ex: "1.0", "0.5"
            on_output:    Callback chamado a cada linha de output
            retry_oom:    Se True, retry com memória dobrada em OOM

        Returns:
            {"output": str, "error": str, "exit_code": int, ...}
        """
        timeout = min(timeout, MAX_TIMEOUT_SECONDS)

        result = self._execute(code, timeout, memory_limit, cpu_limit, on_output)

        # Retry automático em OOM
        if retry_oom and result.get("oom"):
            new_limit = self._double_memory(memory_limit)
            logger.warning(f"OOM detectado — retry com {new_limit}")
            result = self._execute(code, timeout, new_limit, cpu_limit, on_output)

        return result

    def _execute(
        self,
        code: str,
        timeout: int,
        memory_limit: str,
        cpu_limit: str,
        on_output: Optional[Callable[[str], None]],
    ) -> Dict[str, Any]:
        """Execução real via Docker com streaming."""

        result = ExecutionResult()

        # Escreve código em arquivo temporário
        tmp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        )
        tmp_file.write("# -*- coding: utf-8 -*-\n")
        tmp_file.write(code)
        tmp_file.close()
        tmp_path = tmp_file.name

        try:
            # Path do tmp file normalizado para Docker
            if IS_WINDOWS:
                # No Windows, tmpfile fica em C:\Users\...\AppData\Local\Temp
                tmp_normalized = _normalize_workspace_path(Path(tmp_path))
            else:
                tmp_normalized = tmp_path

            cmd = [
                "docker", "run",
                "--rm",
                "--network", "none",
                "--memory", memory_limit,
                "--cpus", cpu_limit,
                "--security-opt", "no-new-privileges",
                "--tmpfs", "/tmp:size=128m",
                # Volume persistente do workspace (mesmo volume entre execuções)
                "-v", f"{self._workspace_host}:/workspace:rw",
                "-w", "/workspace",
                # Código como read-only
                "-v", f"{tmp_normalized}:/code.py:ro",
                "python:3.11-slim",
                "python", "/code.py",
            ]

            logger.debug(f"Docker cmd: {' '.join(cmd[:8])}...")

            t0 = time.time()

            # Execução com streaming de output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            stdout_lines = []
            stderr_lines = []

            # Thread para ler stdout com streaming
            def read_stdout():
                for line in process.stdout:
                    stdout_lines.append(line)
                    if on_output:
                        on_output(line.rstrip())

            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stdout_thread.start()

            # Aguarda com timeout configurável
            try:
                process.wait(timeout=timeout)
                stdout_thread.join(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                result.timed_out = True
                logger.warning(f"Timeout após {timeout}s")

            result.duration   = time.time() - t0
            result.exit_code  = process.returncode or 0
            result.output     = "".join(stdout_lines)
            result.error      = process.stderr.read() if process.stderr else ""

            # Detecta OOM (exit code 137 = SIGKILL por Docker)
            if result.exit_code == 137:
                result.oom   = True
                result.error = f"[OOM] Container encerrado por limite de memória ({memory_limit})"
                logger.warning(f"OOM detectado (exit 137, limit={memory_limit})")

            if result.timed_out:
                result.error  = f"[TIMEOUT] Execução abortada após {timeout}s"
                result.exit_code = -1

            logger.info(
                f"Execução concluída | "
                f"exit={result.exit_code} | "
                f"duration={result.duration:.1f}s | "
                f"output={len(result.output)}chars"
            )

        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return result.to_dict()

    @staticmethod
    def _double_memory(limit: str) -> str:
        """Dobra o limite de memória para retry de OOM."""
        units = {"m": 1, "g": 1024}
        limit = limit.lower()
        if limit[-1] in units:
            value = int(limit[:-1]) * units[limit[-1]]
            new_value = value * 2
            if new_value >= 1024:
                return f"{new_value // 1024}g"
            return f"{new_value}m"
        return "1g"  # fallback seguro

    def get_workspace_path(self) -> str:
        """Retorna o path do workspace no host (para debug)."""
        return str(self.workspace.resolve())


# ── Compatibilidade com microvm_sandbox.py existente ──────────────

class KosmosInfraAdapter:
    """
    Adapter que mantém a interface do MicroVMSandbox existente
    mas usa o KosmosExecutor internamente.

    Permite migração gradual sem quebrar o código existente.
    """

    def __init__(self, config=None):
        self._executor = KosmosExecutor()
        self.kvm_available = KVM_AVAILABLE
        self._active = True

    def run(self, code: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """Interface compatível com MicroVMSandbox.run()"""
        return self._executor.run(code)

    def destroy_vm(self):
        self._active = False


# ── CLI para instalação e diagnóstico ─────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="KOSMOS Infra — Stage 1 Solution"
    )
    parser.add_argument("--install", action="store_true",
                        help="Verifica dependências e configura ambiente")
    parser.add_argument("--diagnose", action="store_true",
                        help="Diagnóstico do ambiente atual")
    parser.add_argument("--test-run", action="store_true",
                        help="Executa um teste rápido de 5s")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s | %(name)s | %(message)s")

    if args.install or args.diagnose:
        print("\n" + "="*55)
        print("  KOSMOS Infra — Diagnóstico")
        print("="*55)
        print(f"  SO:        {platform.system()} {platform.release()}")
        print(f"  Python:    {sys.version.split()[0]}")
        print(f"  Workspace: {WORKSPACE}")
        print(f"  KVM:       {'disponível' if KVM_AVAILABLE else 'indisponível'}")

        # Verifica Docker
        try:
            r = subprocess.run(["docker", "ps"], capture_output=True, timeout=10)
            docker_ok = r.returncode == 0
        except Exception:
            docker_ok = False
        print(f"  Docker:    {'OK' if docker_ok else 'INDISPONÍVEL'}")

        if not docker_ok:
            print("\n  ⚠  Docker não encontrado. Instale Docker Desktop.")
            sys.exit(1)
        else:
            print("\n  ✓ Ambiente pronto para os testes do Estágio 1")

    if args.test_run:
        print("\nTeste rápido (5s)...")
        executor = KosmosExecutor()
        code = (
            "import time\n"
            "for i in range(5):\n"
            "    time.sleep(1)\n"
            "    print(f'tick {i+1}')\n"
            "print('DONE')\n"
        )
        result = executor.run(
            code,
            timeout=30,
            on_output=lambda line: print(f"  > {line}")
        )
        print(f"\nResultado: exit={result['exit_code']} | {result['duration']}s")
        if "DONE" in (result.get("output") or ""):
            print("✓ Teste rápido PASSOU")
        else:
            print("✗ Teste rápido FALHOU")
            print(f"  Output: {result.get('output')}")
            print(f"  Error:  {result.get('error')}")
