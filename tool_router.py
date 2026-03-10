"""
KOSMOS Agent — Tool Router
===========================
Roteador inteligente de ferramentas.
Direciona ações para o executor correto baseado no tipo de tool.
"""

import logging
import os
import shutil
from typing import Dict, Any, Optional

from microvm_sandbox import MicroVMSandbox
from jupyter_executor import JupyterExecutor
from microvm_config import MicroVMConfig

logger = logging.getLogger("kosmos.router")


class ToolRouter:
    """
    Roteador de ferramentas do KOSMOS Agent.

    Rotas disponíveis:
        "python"        → MicroVM Sandbox (isolado via Firecracker)
        "python_local"  → Jupyter Executor (kernel local persistente)
        "python_unsafe" → exec() direto (APENAS para debug)

    Uso:
        router = ToolRouter()
        result = router.execute({"tool": "python", "code": "print(42)"})
    """

    SUPPORTED_TOOLS = ["python", "python_local", "python_unsafe", "write_file", "read_file", "list_files", "mkdir"]

    def __init__(
        self,
        sandbox_config: Optional[MicroVMConfig] = None,
        enable_jupyter: bool = True,
    ):
        # Sandbox Firecracker (execução isolada)
        self.sandbox = MicroVMSandbox(sandbox_config)

        # Jupyter local (executar com estado persistente)
        self._jupyter: Optional[JupyterExecutor] = None
        self._enable_jupyter = enable_jupyter

        # Diretório de trabalho isolado
        self.workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "workspace"))
        if not os.path.exists(self.workspace_root):
            os.makedirs(self.workspace_root, exist_ok=True)

        logger.info(
            f"ToolRouter inicializado. "
            f"Sandbox: Firecracker MicroVM, "
            f"Jupyter: {'enabled' if enable_jupyter else 'disabled'}"
        )

    @property
    def jupyter(self) -> JupyterExecutor:
        """Lazy initialization do Jupyter executor."""
        if self._jupyter is None:
            self._jupyter = JupyterExecutor()
        return self._jupyter

    def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa um plano roteando para a ferramenta correta.

        Args:
            plan: {"tool": str, "code": str, ...}

        Returns:
            {"output": str|None, "error": str|None, "exit_code": int}
        """
        tool = plan.get("tool", "python")
        code = plan.get("code", "")

        # Valida código apenas para ferramentas que executam scripts
        if tool.startswith("python") and (not code or not code.strip()):
            return {
                "output": None,
                "error": "Código vazio",
                "exit_code": -1,
            }

        logger.info(f"Roteando para tool='{tool}' ({len(code)} chars)")

        try:
            if tool == "python":
                return self._route_sandbox(code)

            elif tool == "python_local":
                return self._route_jupyter(code)

            elif tool == "python_unsafe":
                return self._route_unsafe(code)

            elif tool == "write_file":
                return self._route_write_file(plan)

            elif tool == "read_file":
                return self._route_read_file(plan)

            elif tool == "list_files":
                return self._route_list_files(plan)

            elif tool == "mkdir":
                return self._route_mkdir(plan)

            else:
                return {
                    "output": None,
                    "error": f"Ferramenta desconhecida: {tool}. "
                             f"Disponíveis: {self.SUPPORTED_TOOLS}",
                    "exit_code": -1,
                }

        except Exception as e:
            logger.error(f"Erro no roteamento ({tool}): {e}")
            return {
                "output": None,
                "error": str(e),
                "exit_code": -1,
            }

    def _route_sandbox(self, code: str) -> Dict[str, Any]:
        """
        Executa código no sandbox Firecracker microVM.
        Isolamento completo via virtualização de hardware.
        """
        logger.info(f"→ MicroVM Sandbox (Firecracker) [cwd={self.workspace_root}]")
        return self.sandbox.run(code, cwd=self.workspace_root)

    def _route_jupyter(self, code: str) -> Dict[str, Any]:
        """
        Executa código no Jupyter kernel local.
        Estado persistente entre execuções.
        """
        if not self._enable_jupyter:
            return {
                "output": None,
                "error": "Jupyter executor desabilitado",
                "exit_code": -1,
            }

        logger.info("→ Jupyter Executor (local)")
        return self.jupyter.run_code(code)

    def _route_unsafe(self, code: str) -> Dict[str, Any]:
        """
        Executa código via exec() direto.
        ⚠ APENAS para debug — SEM isolamento.
        """
        logger.warning("→ UNSAFE exec() — APENAS para debug!")

        try:
            local_env = {}
            exec(code, {"__builtins__": __builtins__}, local_env)

            # Captura variável 'result' se existir
            output = str(local_env.get("result", local_env))

            return {
                "output": output,
                "error": None,
                "exit_code": 0,
            }

        except Exception as e:
            return {
                "output": None,
                "error": str(e),
                "exit_code": 1,
            }

    def get_status(self) -> Dict[str, Any]:
        """Retorna status de todas as ferramentas."""
        return {
            "sandbox": {
                "type": "Firecracker MicroVM",
                "kvm_available": self.sandbox.kvm_available,
                "active": self.sandbox._active,
            },
            "jupyter": {
                "enabled": self._enable_jupyter,
                "started": self._jupyter._started if self._jupyter else False,
            },
            "supported_tools": self.SUPPORTED_TOOLS,
        }

    def _validate_path(self, path: str) -> str:
        """Valida se o caminho está dentro do workspace e retorna o caminho absoluto."""
        abs_path = os.path.abspath(os.path.join(self.workspace_root, path))
        if not abs_path.startswith(self.workspace_root):
            raise PermissionError(f"Acesso negado: O caminho {path} está fora do workspace.")
        return abs_path

    def _route_write_file(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Cria ou sobrescreve um arquivo no workspace."""
        path = plan.get("path")
        content = plan.get("content", "")
        if not path:
            return {"output": None, "error": "Caminho (path) não especificado", "exit_code": -1}
        
        try:
            full_path = self._validate_path(path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"output": f"Arquivo criado: {path}", "error": None, "exit_code": 0}
        except Exception as e:
            return {"output": None, "error": str(e), "exit_code": 1}

    def _route_read_file(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Lê o conteúdo de um arquivo no workspace."""
        path = plan.get("path")
        if not path:
            return {"output": None, "error": "Caminho (path) não especificado", "exit_code": -1}
        
        try:
            full_path = self._validate_path(path)
            if not os.path.exists(full_path):
                return {"output": None, "error": f"Arquivo não encontrado: {path}", "exit_code": 1}
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"output": content, "error": None, "exit_code": 0}
        except Exception as e:
            return {"output": None, "error": str(e), "exit_code": 1}

    def _route_list_files(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Lista arquivos em um diretório do workspace."""
        path = plan.get("path", ".")
        try:
            full_path = self._validate_path(path)
            if not os.path.isdir(full_path):
                return {"output": None, "error": f"Diretório não encontrado: {path}", "exit_code": 1}
            items = os.listdir(full_path)
            return {"output": "\n".join(items), "error": None, "exit_code": 0}
        except Exception as e:
            return {"output": None, "error": str(e), "exit_code": 1}

    def _route_mkdir(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo diretório no workspace."""
        path = plan.get("path")
        if not path:
            return {"output": None, "error": "Caminho (path) não especificado", "exit_code": -1}
        
        try:
            full_path = self._validate_path(path)
            os.makedirs(full_path, exist_ok=True)
            return {"output": f"Diretório criado: {path}", "error": None, "exit_code": 0}
        except Exception as e:
            return {"output": None, "error": str(e), "exit_code": 1}

    def shutdown(self):
        """Desliga todas as ferramentas."""
        self.sandbox.destroy_vm()
        if self._jupyter:
            self._jupyter.shutdown()
        logger.info("ToolRouter desligado")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
