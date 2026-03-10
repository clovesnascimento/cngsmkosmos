#!/usr/bin/env python3
"""
KOSMOS Agent — Guest-Side Vsock Code Executor
===============================================
Este script roda DENTRO da microVM Firecracker.
Ele escuta conexões vsock e executa código Python recebido.

Protocolo:
  1. Guest escuta em AF_VSOCK na porta 5005
  2. Host conecta via vsock (CONNECT 5005)
  3. Host envia: [4 bytes tamanho] + [JSON payload]
  4. Guest executa o código
  5. Guest retorna: [4 bytes tamanho] + [JSON resultado]

Instalação no guest:
  cp code_executor_guest.py /usr/local/bin/
  chmod +x /usr/local/bin/code_executor_guest.py

  # Systemd service (auto-start no boot)
  cp code_executor.service /etc/systemd/system/
  systemctl enable code_executor
  systemctl start code_executor
"""

import os
import sys
import json
import socket
import signal
import logging
import traceback
import subprocess
import tempfile
import time
from typing import Dict, Any

# ─── Config ───
VSOCK_PORT = 5005
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10 MiB
DEFAULT_TIMEOUT = 30
LOG_FILE = "/var/log/code_executor.log"

# ─── Logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [executor] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a"),
    ] if os.path.isdir(os.path.dirname(LOG_FILE)) else [
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("guest.executor")


class CodeExecutor:
    """Executa código Python de forma isolada dentro do guest."""

    def execute(self, code: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """
        Executa código Python em um subprocess isolado.
        Captura stdout, stderr e exit code.
        """
        try:
            # Escreve código em arquivo temporário
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, dir="/tmp"
            ) as f:
                f.write(code)
                tmp_path = f.name

            # Executa em subprocess com timeout
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": "/root",
                    "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
                },
            )

            return {
                "output": result.stdout if result.stdout else None,
                "error": result.stderr if result.returncode != 0 else None,
                "exit_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "output": None,
                "error": f"Timeout: código excedeu {timeout}s",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "output": None,
                "error": f"Executor error: {str(e)}",
                "exit_code": -1,
            }
        finally:
            # Cleanup
            try:
                os.unlink(tmp_path)
            except (OSError, UnboundLocalError):
                pass


class VsockServer:
    """
    Servidor vsock que escuta conexões do host e executa código.
    Roda dentro da microVM Firecracker.
    """

    # AF_VSOCK = 40 (constante do kernel Linux)
    AF_VSOCK = 40
    VMADDR_CID_ANY = 0xFFFFFFFF  # -1U

    def __init__(self, port: int = VSOCK_PORT):
        self.port = port
        self.executor = CodeExecutor()
        self._running = False
        self._request_count = 0

    def start(self):
        """Inicia o servidor vsock."""
        logger.info(f"Iniciando VsockServer na porta {self.port}...")

        # Cria socket AF_VSOCK
        try:
            sock = socket.socket(self.AF_VSOCK, socket.SOCK_STREAM)
        except OSError:
            logger.warning(
                "AF_VSOCK não disponível. Fallback para AF_INET (debug mode)."
            )
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.port))
            sock.listen(5)
            logger.info(f"Debug mode: escutando em TCP 0.0.0.0:{self.port}")
            self._running = True
            self._accept_loop(sock)
            return

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind: (CID_ANY, port)
        sock.bind((self.VMADDR_CID_ANY, self.port))
        sock.listen(5)

        logger.info(f"VsockServer escutando em vsock port {self.port}")

        self._running = True

        # Signal handlers para graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._accept_loop(sock)

    def _accept_loop(self, sock: socket.socket):
        """Loop de aceitação de conexões."""
        sock.settimeout(1.0)  # Permite checkar _running periodicamente

        while self._running:
            try:
                conn, addr = sock.accept()
                self._request_count += 1
                logger.info(
                    f"Conexão #{self._request_count} de {addr}"
                )
                self._handle_connection(conn)
            except socket.timeout:
                continue
            except OSError as e:
                if self._running:
                    logger.error(f"Accept error: {e}")
                break

        sock.close()
        logger.info("VsockServer encerrado")

    def _handle_connection(self, conn: socket.socket):
        """Processa uma conexão: recebe código, executa, retorna resultado."""
        conn.settimeout(DEFAULT_TIMEOUT + 5)

        try:
            # ─── Recebe payload ───
            raw_length = self._recv_exact(conn, 4)
            if not raw_length:
                return

            payload_length = int.from_bytes(raw_length, byteorder="big")

            if payload_length > MAX_PAYLOAD_SIZE:
                self._send_error(conn, "Payload excede limite")
                return

            raw_payload = self._recv_exact(conn, payload_length)
            if not raw_payload:
                return

            payload = json.loads(raw_payload.decode("utf-8"))

            logger.info(
                f"Request: action={payload.get('action')}, "
                f"code_size={len(payload.get('code', ''))}"
            )

            # ─── Executa ───
            action = payload.get("action", "execute")
            timeout = payload.get("timeout", DEFAULT_TIMEOUT)

            if action == "execute":
                code = payload.get("code", "")
                result = self.executor.execute(code, timeout=timeout)

            elif action == "ping":
                result = {
                    "output": "pong",
                    "error": None,
                    "exit_code": 0,
                    "request_count": self._request_count,
                }

            elif action == "info":
                import platform
                result = {
                    "output": json.dumps({
                        "python": sys.version,
                        "platform": platform.platform(),
                        "hostname": platform.node(),
                        "requests_served": self._request_count,
                    }),
                    "error": None,
                    "exit_code": 0,
                }

            else:
                result = {
                    "output": None,
                    "error": f"Ação desconhecida: {action}",
                    "exit_code": -1,
                }

            # ─── Envia resultado ───
            response = json.dumps(result).encode("utf-8")
            length = len(response).to_bytes(4, byteorder="big")
            conn.sendall(length + response)

            logger.info(
                f"Response: exit_code={result.get('exit_code')}, "
                f"output_size={len(result.get('output', '') or '')}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON inválido: {e}")
            self._send_error(conn, f"JSON inválido: {e}")

        except socket.timeout:
            logger.error("Connection timeout")
            self._send_error(conn, "Timeout na comunicação")

        except Exception as e:
            logger.error(f"Handler error: {e}\n{traceback.format_exc()}")
            self._send_error(conn, str(e))

        finally:
            conn.close()

    def _send_error(self, conn: socket.socket, message: str):
        """Envia mensagem de erro."""
        try:
            result = json.dumps({
                "output": None,
                "error": message,
                "exit_code": -1,
            }).encode("utf-8")
            length = len(result).to_bytes(4, byteorder="big")
            conn.sendall(length + result)
        except Exception:
            pass

    @staticmethod
    def _recv_exact(conn: socket.socket, n: int) -> bytes:
        """Recebe exatamente N bytes."""
        data = b""
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                return b""
            data += chunk
        return data

    def _handle_signal(self, signum, frame):
        """Graceful shutdown."""
        logger.info(f"Signal {signum} recebido. Encerrando...")
        self._running = False

    def stop(self):
        """Para o servidor."""
        self._running = False


def main():
    """Entry point para o guest executor."""
    import argparse

    parser = argparse.ArgumentParser(
        description="KOSMOS Guest Code Executor (vsock server)"
    )
    parser.add_argument(
        "--port", type=int, default=VSOCK_PORT,
        help=f"Porta vsock (default: {VSOCK_PORT})"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Modo debug (TCP ao invés de vsock)"
    )
    args = parser.parse_args()

    print(f"""
╔════════════════════════════════════════╗
║  KOSMOS Guest Code Executor v1.0      ║
║  Port: {args.port:<5}                         ║
║  Mode: {'TCP/Debug' if args.debug else 'AF_VSOCK':<14}                ║
╚════════════════════════════════════════╝
    """)

    server = VsockServer(port=args.port)
    server.start()


if __name__ == "__main__":
    main()
