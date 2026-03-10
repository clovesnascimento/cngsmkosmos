#!/usr/bin/env bash
# ═══════════════════════════════════════════════════
# KOSMOS Agent — Setup Rootfs para Firecracker Guest
# ═══════════════════════════════════════════════════
# Cria um rootfs ext4 customizado com Python, Jupyter
# e o code_executor_guest.py pré-instalado.
#
# Pré-requisitos:
#   - debootstrap (Debian/Ubuntu)
#   - qemu-user-static (para cross-arch)
#   - root ou sudo
#
# Uso:
#   sudo ./setup_rootfs.sh [--size 2G] [--arch amd64]
#
# Output:
#   ./kosmos_rootfs.ext4 — rootfs pronto para Firecracker
# ═══════════════════════════════════════════════════

set -euo pipefail

# ─── Defaults ───
ROOTFS_SIZE="${1:-2G}"
ARCH="${2:-amd64}"
ROOTFS_IMAGE="kosmos_rootfs.ext4"
ROOTFS_DIR="rootfs_build"
DISTRO="bookworm"  # Debian 12

echo "╔════════════════════════════════════════╗"
echo "║  KOSMOS Rootfs Builder v1.0            ║"
echo "║  Size: ${ROOTFS_SIZE}                          ║"
echo "║  Arch: ${ARCH}                         ║"
echo "║  Distro: ${DISTRO}                    ║"
echo "╚════════════════════════════════════════╝"

# ─── 1. Cria a imagem ext4 ───
echo ""
echo "[1/7] Criando imagem ext4 (${ROOTFS_SIZE})..."
truncate -s "${ROOTFS_SIZE}" "${ROOTFS_IMAGE}"
mkfs.ext4 -F "${ROOTFS_IMAGE}"

# ─── 2. Monta a imagem ───
echo "[2/7] Montando imagem..."
mkdir -p "${ROOTFS_DIR}"
mount -o loop "${ROOTFS_IMAGE}" "${ROOTFS_DIR}"

# Trap para cleanup em caso de falha
cleanup() {
    echo ""
    echo "[cleanup] Desmontando..."
    umount -l "${ROOTFS_DIR}" 2>/dev/null || true
    rmdir "${ROOTFS_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

# ─── 3. Debootstrap ───
echo "[3/7] Instalando sistema base (debootstrap)..."
debootstrap --arch="${ARCH}" "${DISTRO}" "${ROOTFS_DIR}" http://deb.debian.org/debian

# ─── 4. Instala Python e dependências ───
echo "[4/7] Instalando Python e dependências..."
chroot "${ROOTFS_DIR}" /bin/bash -c "
    apt-get update -qq
    apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-venv \
        openssh-server \
        iproute2 \
        iputils-ping \
        curl \
        ca-certificates \
        2>/dev/null

    # Instala dependências Python
    pip3 install --break-system-packages \
        jupyter_client \
        ipykernel \
        numpy \
        2>/dev/null

    # Instala kernel Jupyter
    python3 -m ipykernel install --name python3 --user
"

# ─── 5. Configura rede ───
echo "[5/7] Configurando rede..."
cat > "${ROOTFS_DIR}/etc/network/interfaces" << 'NETEOF'
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
    address 172.16.0.2
    netmask 255.255.255.252
    gateway 172.16.0.1
NETEOF

echo "nameserver 8.8.8.8" > "${ROOTFS_DIR}/etc/resolv.conf"
echo "kosmos-vm" > "${ROOTFS_DIR}/etc/hostname"

# ─── 6. Instala o Code Executor ───
echo "[6/7] Instalando KOSMOS Code Executor..."

# Copia o executor para o guest
cp "$(dirname "$0")/code_executor_guest.py" \
   "${ROOTFS_DIR}/usr/local/bin/code_executor_guest.py"
chmod +x "${ROOTFS_DIR}/usr/local/bin/code_executor_guest.py"

# Cria systemd service para auto-start
cat > "${ROOTFS_DIR}/etc/systemd/system/kosmos-executor.service" << 'SVCEOF'
[Unit]
Description=KOSMOS Code Executor (vsock server)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/code_executor_guest.py --port 5005
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

# Security hardening dentro do guest
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/tmp

[Install]
WantedBy=multi-user.target
SVCEOF

# Habilita o service
chroot "${ROOTFS_DIR}" /bin/bash -c "
    systemctl enable kosmos-executor.service 2>/dev/null || true
"

# ─── 7. Configurações finais ───
echo "[7/7] Configurações finais..."

# Password root (para debug — remover em prod)
chroot "${ROOTFS_DIR}" /bin/bash -c "
    echo 'root:root' | chpasswd
"

# SSH config (para debug)
mkdir -p "${ROOTFS_DIR}/root/.ssh"
chmod 700 "${ROOTFS_DIR}/root/.ssh"

# Auto-login no console serial (para debug)
mkdir -p "${ROOTFS_DIR}/etc/systemd/system/serial-getty@ttyS0.service.d"
cat > "${ROOTFS_DIR}/etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf" << 'LOGINEOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
LOGINEOF

# Script de setup de rede no boot
cat > "${ROOTFS_DIR}/usr/local/bin/fcnet-setup.sh" << 'FCNETEOF'
#!/bin/bash
# Firecracker network setup
ip addr add 172.16.0.2/30 dev eth0 2>/dev/null || true
ip link set eth0 up 2>/dev/null || true
ip route add default via 172.16.0.1 dev eth0 2>/dev/null || true
FCNETEOF
chmod +x "${ROOTFS_DIR}/usr/local/bin/fcnet-setup.sh"

# Cleanup
chroot "${ROOTFS_DIR}" /bin/bash -c "
    apt-get clean
    rm -rf /var/lib/apt/lists/*
    rm -rf /tmp/*
"

# ─── Done ───
echo ""
echo "╔════════════════════════════════════════╗"
echo "║  ✅ Rootfs criado com sucesso!         ║"
echo "║                                        ║"
echo "║  Arquivo: ${ROOTFS_IMAGE}        ║"
echo "║  Tamanho: $(du -h ${ROOTFS_IMAGE} | cut -f1)                         ║"
echo "║                                        ║"
echo "║  Inclui:                               ║"
echo "║  • Python 3 + pip                      ║"
echo "║  • jupyter_client + ipykernel          ║"
echo "║  • KOSMOS Code Executor (vsock:5005)   ║"
echo "║  • Rede pré-configurada (172.16.0.2)   ║"
echo "║  • SSH server                          ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Uso com Firecracker:"
echo "  microvm_config.py → rootfs_path = '$(pwd)/${ROOTFS_IMAGE}'"
