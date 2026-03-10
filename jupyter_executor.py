"""
KOSMOS Agent — Jupyter Executor
================================
Execução real de código via jupyter_client com KernelManager.
Suporta persistência de estado entre execuções (mesmo kernel).
"""

import logging
import queue
from typing import Dict, Any, Optional

logger = logging.getLogger("kosmos.jupyter")


class JupyterExecutor:
    """
    Executor de código Python usando jupyter_client.

    Mantém um kernel Jupyter persistente para execução
    com estado compartilhado entre chamadas.

    Uso:
        executor = JupyterExecutor()
        result = executor.run_code("x = 42")
        result = executor.run_code("print(x)")  # x ainda existe
        executor.shutdown()
    """

    def __init__(self, kernel_name: str = "python3", timeout: int = 30):
        self.kernel_name = kernel_name
        self.timeout = timeout
        self.km = None
        self.kc = None
        self._started = False

    def start(self):
        """Inicia o kernel Jupyter."""
        if self._started:
            return

        try:
            from jupyter_client import KernelManager

            self.km = KernelManager(kernel_name=self.kernel_name)
            self.km.start_kernel()

            self.kc = self.km.client()
            self.kc.start_channels()

            # Aguarda kernel ficar pronto
            self.kc.wait_for_ready(timeout=self.timeout)

            self._started = True
            logger.info(f"Kernel Jupyter '{self.kernel_name}' iniciado")

        except ImportError:
            logger.error("jupyter_client não instalado. Usando fallback.")
            raise
        except Exception as e:
            logger.error(f"Falha ao iniciar kernel: {e}")
            raise

    def run_code(self, code: str) -> Dict[str, Any]:
        """
        Executa código no kernel Jupyter.

        Retorna:
            {
                "output": str | None,
                "error": str | None,
                "data": dict | None,  # rich output (HTML, imagens, etc.)
                "exit_code": int
            }
        """
        if not self._started:
            self.start()

        try:
            msg_id = self.kc.execute(code)

            output_parts = []
            error_parts = []
            data_output = None

            while True:
                try:
                    msg = self.kc.get_iopub_msg(timeout=self.timeout)
                except queue.Empty:
                    return {
                        "output": None,
                        "error": f"Timeout após {self.timeout}s",
                        "data": None,
                        "exit_code": -1,
                    }

                # Filtra mensagens deste request
                if msg["parent_header"].get("msg_id") != msg_id:
                    continue

                msg_type = msg["msg_type"]
                content = msg["content"]

                if msg_type == "stream":
                    output_parts.append(content.get("text", ""))

                elif msg_type == "execute_result":
                    data_output = content.get("data", {})
                    text = data_output.get("text/plain", "")
                    if text:
                        output_parts.append(text)

                elif msg_type == "display_data":
                    data_output = content.get("data", {})

                elif msg_type == "error":
                    traceback = content.get("traceback", [])
                    error_parts.append("\n".join(traceback))

                elif msg_type == "status":
                    if content.get("execution_state") == "idle":
                        break

            output = "\n".join(output_parts) if output_parts else None
            error = "\n".join(error_parts) if error_parts else None

            return {
                "output": output,
                "error": error,
                "data": data_output,
                "exit_code": 1 if error else 0,
            }

        except Exception as e:
            return {
                "output": None,
                "error": str(e),
                "data": None,
                "exit_code": -1,
            }

    def restart_kernel(self):
        """Reinicia o kernel (limpa estado)."""
        if self.km and self._started:
            self.km.restart_kernel()
            self.kc = self.km.client()
            self.kc.start_channels()
            self.kc.wait_for_ready(timeout=self.timeout)
            logger.info("Kernel reiniciado")

    def shutdown(self):
        """Desliga o kernel Jupyter."""
        if self.kc:
            self.kc.stop_channels()
        if self.km and self._started:
            self.km.shutdown_kernel(now=True)
            self._started = False
            logger.info("Kernel Jupyter desligado")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()

    def __del__(self):
        if self._started:
            self.shutdown()
