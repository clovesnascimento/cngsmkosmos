"""
KOSMOS Agent — Sandbox Firecracker MicroVM
==========================================
Gerencia o ciclo de vida completo de microVMs Firecracker para execução
isolada de código. Comunicação host↔guest via vsock.

Fluxo:
  1. Inicia processo Firecracker (--api-sock)
  2. Configura via API REST (boot-source, drives, network, vsock)
  3. Starta a microVM (InstanceStart)
  4. Envia código via vsock (AF_UNIX → AF_VSOCK)
  5. Recebe resultado
  6. Destrói a VM + cleanup

Fallback: quando KVM não está disponível (ex: Windows), usa subprocess.
"""

import os
import json
import uuid
import time
import socket
import signal
import logging
import subprocess
import tempfile
from typing import Dict, Any, Optional
from dataclasses import dataclass

from microvm_config import MicroVMConfig, FirecrackerPaths

logger = logging.getLogger("kosmos.sandbox")


# ─────────────────────────────────────────────
# VSOCK CLIENT (host-side)
# ─────────────────────────────────────────────

class VsockClient:
    """
    Comunica com o guest via vsock (AF_UNIX no host).
    Protocolo:
      Host → connect ao uds_path
      Host → envia "CONNECT <port>\n"
      Host → lê "OK <port>\n"
      Host → envia payload JSON
      Host → recebe resultado JSON
    """

    def __init__(self, uds_path: str, port: int, timeout: int = 30):
        self.uds_path = uds_path
        self.port = port
        self.timeout = timeout

    def send_code(self, code: str) -> Dict[str, Any]:
        """Envia código para execução dentro da microVM via vsock."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        try:
            sock.connect(self.uds_path)

            # Protocolo Firecracker vsock: CONNECT <port>\n
            connect_cmd = f"CONNECT {self.port}\n"
            sock.sendall(connect_cmd.encode("utf-8"))

            # Espera acknowledgement: "OK <port>\n"
            ack = b""
            while b"\n" not in ack:
                chunk = sock.recv(256)
                if not chunk:
                    raise ConnectionError("Vsock: conexão fechada antes do ACK")
                ack += chunk

            ack_str = ack.decode("utf-8").strip()
            if not ack_str.startswith("OK"):
                raise ConnectionError(f"Vsock: ACK inválido: {ack_str}")

            logger.info(f"Vsock conectado: {ack_str}")

            # Envia payload JSON com o código
            payload = json.dumps({
                "action": "execute",
                "code": code,
                "timeout": self.timeout,
            })
            payload_bytes = payload.encode("utf-8")
            # Protocolo: 4 bytes de tamanho + payload
            length = len(payload_bytes).to_bytes(4, byteorder="big")
            sock.sendall(length + payload_bytes)

            # Recebe resultado
            raw_length = self._recv_exact(sock, 4)
            response_length = int.from_bytes(raw_length, byteorder="big")
            raw_response = self._recv_exact(sock, response_length)

            result = json.loads(raw_response.decode("utf-8"))
            return result

        except socket.timeout:
            return {
                "output": None,
                "error": f"Timeout após {self.timeout}s",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "output": None,
                "error": str(e),
                "exit_code": -1,
            }
        finally:
            sock.close()

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes:
        """Recebe exatamente N bytes do socket."""
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Conexão fechada durante recebimento")
            data += chunk
        return data


# ─────────────────────────────────────────────
# FIRECRACKER API CLIENT
# ─────────────────────────────────────────────

class FirecrackerAPIClient:
    """
    Cliente para a API REST do Firecracker via Unix socket.
    Endpoints: /boot-source, /drives, /network-interfaces, /vsock, /actions, etc.
    """

    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    def put(self, endpoint: str, payload: dict) -> dict:
        """PUT request via Unix socket usando HTTP/1.1 raw."""
        body = json.dumps(payload)
        request = (
            f"PUT {endpoint} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Accept: application/json\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
            f"{body}"
        )

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5)

        try:
            sock.connect(self.socket_path)
            sock.sendall(request.encode("utf-8"))

            response = b""
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                except socket.timeout:
                    break

            response_str = response.decode("utf-8")
            logger.debug(f"API {endpoint}: {response_str[:200]}")

            # Parse status code
            status_line = response_str.split("\r\n")[0]
            status_code = int(status_line.split(" ")[1])

            # Parse body
            body_start = response_str.find("\r\n\r\n")
            response_body = response_str[body_start + 4:] if body_start > 0 else ""

            return {
                "status_code": status_code,
                "body": response_body,
                "success": 200 <= status_code < 300,
            }

        finally:
            sock.close()

    def configure_vm(self, config: MicroVMConfig) -> bool:
        """Configura a microVM usando os payloads da config."""
        payloads = config.get_api_payloads()

        for endpoint, payload in payloads.items():
            if endpoint == "/actions":
                continue  # Start separadamente

            result = self.put(endpoint, payload)
            if not result["success"]:
                logger.error(f"Falha ao configurar {endpoint}: {result}")
                return False

            logger.info(f"Configurado {endpoint}: OK")
            time.sleep(0.01)  # Firecracker processa async

        return True

    def start_vm(self) -> bool:
        """Inicia a microVM."""
        result = self.put("/actions", {"action_type": "InstanceStart"})
        return result["success"]


# ─────────────────────────────────────────────
# MICROVM SANDBOX
# ─────────────────────────────────────────────

class MicroVMSandbox:
    """
    Sandbox de execução usando Firecracker microVMs.

    Uso:
        sandbox = MicroVMSandbox()
        result = sandbox.run("print('Hello from microVM!')")
        print(result)
    """

    def __init__(self, config: Optional[MicroVMConfig] = None):
        self.config = config or MicroVMConfig()
        self.paths = self.config.paths
        self.process: Optional[subprocess.Popen] = None
        self.api_client: Optional[FirecrackerAPIClient] = None
        self.vsock_client: Optional[VsockClient] = None
        self._active = False

        # Garante que os diretórios existem
        os.makedirs(self.paths.api_socket_dir, exist_ok=True)
        os.makedirs(self.paths.log_dir, exist_ok=True)

    @property
    def kvm_available(self) -> bool:
        """Verifica se KVM está disponível no host."""
        return os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)

    def create_vm(self) -> bool:
        """
        Cria e starta uma microVM Firecracker.
        Retorna True se sucesso.
        """
        if not self.kvm_available:
            logger.warning("KVM não disponível. Usando fallback subprocess.")
            return False

        socket_path = self.paths.socket_path(self.config.vm_id)

        # Remove socket antigo
        if os.path.exists(socket_path):
            os.remove(socket_path)

        # Inicia processo Firecracker
        cmd = [
            self.paths.firecracker_binary,
            "--api-sock", socket_path,
        ]

        log_path = self.paths.log_path(self.config.vm_id)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=open(log_path, "w"),
                stderr=subprocess.STDOUT,
            )

            # Aguarda socket ficar disponível
            for _ in range(50):
                if os.path.exists(socket_path):
                    break
                time.sleep(0.1)
            else:
                raise TimeoutError("Firecracker socket não criado em tempo")

            # Configura via API
            self.api_client = FirecrackerAPIClient(socket_path)

            if not self.api_client.configure_vm(self.config):
                raise RuntimeError("Falha na configuração da microVM")

            # Starta a VM
            if not self.api_client.start_vm():
                raise RuntimeError("Falha ao startar microVM")

            logger.info(f"MicroVM {self.config.vm_id} iniciada com sucesso")

            # Aguarda guest boot
            time.sleep(2)

            # Inicializa cliente vsock
            vsock_uds = os.path.join(
                os.path.dirname(socket_path),
                self.config.vsock.uds_path
            )
            self.vsock_client = VsockClient(
                uds_path=vsock_uds,
                port=self.config.vsock.code_execution_port,
                timeout=self.config.execution.timeout_seconds,
            )

            self._active = True
            return True

        except Exception as e:
            logger.error(f"Falha ao criar microVM: {e}")
            self.destroy_vm()
            return False

    def execute_in_vm(self, code: str) -> Dict[str, Any]:
        """
        Executa código dentro da microVM ativa via vsock.
        """
        if not self._active or not self.vsock_client:
            return {
                "output": None,
                "error": "MicroVM não está ativa",
                "exit_code": -1,
            }

        return self.vsock_client.send_code(code)

    def destroy_vm(self):
        """Destrói a microVM e faz cleanup."""
        self._active = False

        if self.process:
            try:
                self.process.send_signal(signal.SIGTERM)
                self.process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self.process.kill()
                    self.process.wait(timeout=2)
                except Exception:
                    pass
            self.process = None

        # Cleanup socket
        socket_path = self.paths.socket_path(self.config.vm_id)
        if os.path.exists(socket_path):
            try:
                os.remove(socket_path)
            except OSError:
                pass

        logger.info(f"MicroVM {self.config.vm_id} destruída")

    def run(self, code: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """
        API de alto nível: create → execute → destroy.
        Com fallback automático para subprocess quando KVM não disponível.
        """
        # Fallback para ambientes sem KVM (ex: Windows)
        if not self.kvm_available:
            return self._fallback_execute(code, cwd)

        try:
            if not self._active:
                if not self.create_vm():
                    return self._fallback_execute(code)

            return self.execute_in_vm(code) # VM isolation is internal

        except Exception as e:
            logger.error(f"Erro na execução microVM: {e}")
            return {
                "output": None,
                "error": str(e),
                "exit_code": -1,
            }

    def _fallback_execute(self, code: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """
        Fallback: executa código via subprocess Python isolado.
        Usado quando KVM/Firecracker não está disponível.
        """
        logger.info("Usando fallback subprocess (KVM indisponível)")

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                # Cookie de encoding para Python no Windows
                f.write("# -*- coding: utf-8 -*-\n")
                f.write(code)
                tmp_path = f.name

            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"

            result = subprocess.run(
                ["python", tmp_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.config.execution.timeout_seconds,
                env=env,
                cwd=cwd or os.getcwd()
            )

            return {
                "output": result.stdout or None,
                "error": result.stderr if result.returncode != 0 else None,
                "exit_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "output": None,
                "error": f"Timeout após {self.config.execution.timeout_seconds}s",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "output": None,
                "error": str(e),
                "exit_code": -1,
            }
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy_vm()

    def __del__(self):
        if self._active:
            self.destroy_vm()


# ─────────────────────────────────────────────
# MICROVM POOL (para ToT paralelo)
# ─────────────────────────────────────────────

class MicroVMPool:
    """
    Pool de microVMs para execução paralela.
    Usado pelo Tree of Thoughts para testar múltiplas hipóteses.
    """

    def __init__(self, pool_size: int = 4, base_config: Optional[MicroVMConfig] = None):
        self.pool_size = pool_size
        self.base_config = base_config or MicroVMConfig()
        self._pool: list[MicroVMSandbox] = []

    def initialize(self):
        """Pré-cria pool de sandboxes."""
        for i in range(self.pool_size):
            config = MicroVMConfig(
                vm_id=f"kosmos-pool-{i}-{uuid.uuid4().hex[:8]}",
                kernel=self.base_config.kernel,
                rootfs=self.base_config.rootfs,
                machine=self.base_config.machine,
                vsock=self.base_config.vsock,
                execution=self.base_config.execution,
                paths=self.base_config.paths,
            )
            # Cada VM precisa de um CID único
            config.vsock.guest_cid = 3 + i

            sandbox = MicroVMSandbox(config)
            self._pool.append(sandbox)

        logger.info(f"Pool de {self.pool_size} sandboxes inicializado")

    def get_sandbox(self, index: int) -> MicroVMSandbox:
        """Obtém sandbox do pool por índice."""
        if index >= len(self._pool):
            raise IndexError(f"Índice {index} fora do pool (tamanho={len(self._pool)})")
        return self._pool[index]

    def execute_parallel(self, codes: list[str]) -> list[Dict[str, Any]]:
        """
        Executa múltiplos códigos em paralelo, um por sandbox.
        """
        import concurrent.futures

        results = [None] * len(codes)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.pool_size) as pool:
            futures = {}
            for i, code in enumerate(codes):
                sandbox = self.get_sandbox(i % self.pool_size)
                future = pool.submit(sandbox.run, code)
                futures[future] = i

            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = {
                        "output": None,
                        "error": str(e),
                        "exit_code": -1,
                    }

        return results

    def shutdown(self):
        """Destrói todas as sandboxes do pool."""
        for sandbox in self._pool:
            sandbox.destroy_vm()
        self._pool.clear()
        logger.info("Pool de sandboxes encerrado")

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
