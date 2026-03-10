"""
KOSMOS Agent — Configuração de MicroVMs Firecracker
====================================================
Configurações centralizadas para criação e gerenciamento de microVMs.
Paths, recursos, rede, vsock e timeouts.
"""

import os
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KernelConfig:
    """Configuração do kernel da microVM."""
    kernel_image_path: str = "/opt/firecracker/vmlinux"
    boot_args: str = "console=ttyS0 reboot=k panic=1 pci=off"


@dataclass
class RootfsConfig:
    """Configuração do sistema de arquivos root."""
    rootfs_path: str = "/opt/firecracker/rootfs.ext4"
    is_read_only: bool = False
    drive_id: str = "rootfs"


@dataclass
class MachineConfig:
    """Recursos da microVM."""
    vcpu_count: int = 1
    mem_size_mib: int = 128
    smt: bool = False  # Simultaneous Multithreading


@dataclass
class NetworkConfig:
    """Configuração de rede."""
    iface_id: str = "net1"
    host_dev_name: str = "tap0"
    guest_mac: str = "06:00:AC:10:00:02"
    tap_ip: str = "172.16.0.1"
    guest_ip: str = "172.16.0.2"
    mask_short: str = "/30"


@dataclass
class VsockConfig:
    """Configuração do canal vsock (host ↔ guest)."""
    guest_cid: int = 3
    uds_path: str = "./v.sock"
    # Porta padrão para o serviço de execução de código dentro da VM
    code_execution_port: int = 5005


@dataclass
class JailerConfig:
    """Configuração do Jailer (sandboxing em produção)."""
    enabled: bool = False
    jailer_binary: str = "/usr/bin/jailer"
    chroot_base_dir: str = "/srv/jailer"
    uid: int = 1000
    gid: int = 1000
    netns: Optional[str] = None
    daemonize: bool = True
    new_pid_ns: bool = True
    cgroup_version: str = "2"


@dataclass
class ExecutionConfig:
    """Limites de execução."""
    timeout_seconds: int = 30
    max_output_bytes: int = 1_048_576  # 1 MiB
    max_concurrent_vms: int = 4


@dataclass
class FirecrackerPaths:
    """Paths do binário Firecracker e socket."""
    firecracker_binary: str = "/usr/bin/firecracker"
    api_socket_dir: str = "/tmp/firecracker"
    log_dir: str = "/tmp/firecracker/logs"

    def socket_path(self, vm_id: str) -> str:
        return os.path.join(self.api_socket_dir, f"{vm_id}.sock")

    def log_path(self, vm_id: str) -> str:
        return os.path.join(self.log_dir, f"{vm_id}.log")


@dataclass
class MicroVMConfig:
    """
    Configuração master de uma microVM Firecracker.
    Agrupa todas as sub-configurações.
    """
    vm_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kernel: KernelConfig = field(default_factory=KernelConfig)
    rootfs: RootfsConfig = field(default_factory=RootfsConfig)
    machine: MachineConfig = field(default_factory=MachineConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    vsock: VsockConfig = field(default_factory=VsockConfig)
    jailer: JailerConfig = field(default_factory=JailerConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    paths: FirecrackerPaths = field(default_factory=FirecrackerPaths)

    def to_firecracker_config(self) -> dict:
        """
        Gera o JSON de configuração completo para --config-file do Firecracker.
        Pode ser usado ao invés de chamadas individuais à API.
        """
        config = {
            "boot-source": {
                "kernel_image_path": self.kernel.kernel_image_path,
                "boot_args": self.kernel.boot_args,
            },
            "drives": [
                {
                    "drive_id": self.rootfs.drive_id,
                    "path_on_host": self.rootfs.rootfs_path,
                    "is_root_device": True,
                    "is_read_only": self.rootfs.is_read_only,
                }
            ],
            "machine-config": {
                "vcpu_count": self.machine.vcpu_count,
                "mem_size_mib": self.machine.mem_size_mib,
                "smt": self.machine.smt,
            },
            "network-interfaces": [
                {
                    "iface_id": self.network.iface_id,
                    "guest_mac": self.network.guest_mac,
                    "host_dev_name": self.network.host_dev_name,
                }
            ],
            "vsock": {
                "guest_cid": self.vsock.guest_cid,
                "uds_path": self.vsock.uds_path,
            },
        }
        return config

    def get_api_payloads(self) -> dict:
        """
        Gera os payloads individuais para cada endpoint da API Firecracker.
        Retorna dict com chave = endpoint, valor = payload.
        """
        return {
            "/boot-source": {
                "kernel_image_path": self.kernel.kernel_image_path,
                "boot_args": self.kernel.boot_args,
            },
            "/drives/rootfs": {
                "drive_id": self.rootfs.drive_id,
                "path_on_host": self.rootfs.rootfs_path,
                "is_root_device": True,
                "is_read_only": self.rootfs.is_read_only,
            },
            "/machine-config": {
                "vcpu_count": self.machine.vcpu_count,
                "mem_size_mib": self.machine.mem_size_mib,
                "smt": self.machine.smt,
            },
            f"/network-interfaces/{self.network.iface_id}": {
                "iface_id": self.network.iface_id,
                "guest_mac": self.network.guest_mac,
                "host_dev_name": self.network.host_dev_name,
            },
            "/vsock": {
                "guest_cid": self.vsock.guest_cid,
                "uds_path": self.vsock.uds_path,
            },
            "/actions": {
                "action_type": "InstanceStart",
            },
        }
