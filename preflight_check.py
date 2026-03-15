#!/usr/bin/env python3
"""
KOSMOS Agent — Pre-Flight Security Check v2.2
=============================================
Correções v2.2:
  - Detecção correta de Docker Desktop no Windows (MINGW64/Git Bash)
  - Flag --dev-mode para Windows sem Docker
  - Detecção de plataforma (Windows / Linux / WSL2)
  - Guia de correção específico por plataforma (--fix-guide)

Uso:
    python preflight_check.py               # Check padrão
    python preflight_check.py --dev-mode    # Windows sem Docker (só dev)
    python preflight_check.py --fix-guide   # Guia de correção passo a passo
    python preflight_check.py --strict      # CI/CD: exit 1 se falhar
"""

import os
import sys
import platform
import subprocess
import argparse
from typing import Tuple

RESET  = "\033[0m"; GREEN  = "\033[92m"; YELLOW = "\033[93m"
RED    = "\033[91m"; CYAN   = "\033[96m"; BOLD   = "\033[1m"
OK   = f"{GREEN}✓ OK{RESET}"
WARN = f"{YELLOW}⚠ AVISO{RESET}"
FAIL = f"{RED}✗ FALHA{RESET}"
INFO = f"{CYAN}ℹ INFO{RESET}"


def check(label, result, warn_only=False, detail=""):
    status = OK if result else (WARN if warn_only else FAIL)
    print(f"  {status}  {label}")
    if detail:
        print(f"         {CYAN}{detail}{RESET}")
    return status, result


def section(title):
    bar = "─" * max(1, 50 - len(title))
    print(f"\n{BOLD}{CYAN}── {title} {bar}{RESET}")


def detect_platform():
    system = platform.system()
    is_windows = system == "Windows"
    is_linux   = system == "Linux"
    is_wsl = False
    if is_linux:
        try:
            v = open("/proc/version").read().lower()
            is_wsl = "microsoft" in v or "wsl" in v
        except OSError:
            pass
    is_mingw = "MINGW" in os.environ.get("MSYSTEM", "") or \
               "MINGW" in os.environ.get("TERM_PROGRAM", "")
    return dict(system=system, is_windows=is_windows, is_linux=is_linux,
                is_wsl=is_wsl, is_mingw=is_mingw, release=platform.release())


def check_docker(plat):
    """Detecta Docker com múltiplas estratégias — Windows, WSL2, Linux."""
    use_shell = plat["is_windows"] or plat["is_mingw"]
    for cmd in [["docker", "ps"], ["docker.exe", "ps"]]:
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=8, shell=use_shell)
            if r.returncode == 0:
                return True, "Docker daemon respondeu"
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    # Verifica named pipe no Windows
    if plat["is_windows"] or plat["is_mingw"]:
        pipe = r"\\.\pipe\docker_engine"
        if os.path.exists(pipe):
            return True, f"Docker Engine pipe encontrado"
    # Verifica socket no Linux/WSL
    if plat["is_linux"] or plat["is_wsl"]:
        for sock in ["/var/run/docker.sock", "/run/docker.sock"]:
            if os.path.exists(sock):
                return True, f"Docker socket: {sock}"
    return False, "Docker não encontrado ou daemon parado"


def check_kvm(plat):
    if plat["is_windows"] and not plat["is_wsl"]:
        return False, "Windows host: KVM não suportado nativamente"
    kvm_path = "/dev/kvm"
    if os.path.exists(kvm_path):
        if os.access(kvm_path, os.R_OK | os.W_OK):
            return True, "KVM disponível e acessível"
        return False, "KVM existe mas sem permissão — execute: sudo usermod -aG kvm $USER"
    return False, "KVM não encontrado"


def print_fix_guide(plat, issues_text):
    print(f"\n{BOLD}{YELLOW}{'='*60}")
    print(f"  GUIA DE CORREÇÃO — {plat['system']} {'(MINGW/Git Bash)' if plat['is_mingw'] else ''}")
    print(f"{'='*60}{RESET}")

    if plat["is_windows"] or plat["is_mingw"]:
        print(f"""
{BOLD}[1] Instalar Docker Desktop (recomendado){RESET}
    • Baixe em: {CYAN}https://www.docker.com/products/docker-desktop/{RESET}
    • Instale e reinicie
    • Abra Docker Desktop e aguarde o ícone ficar estável na barra
    • Teste: {CYAN}docker ps{RESET}  (em qualquer terminal)

{BOLD}[2] Alternativa: WSL2 + Docker Engine{RESET}
    No PowerShell (Admin):
      {CYAN}wsl --install{RESET}
      {CYAN}wsl --set-default-version 2{RESET}
    Dentro do WSL2:
      {CYAN}curl -fsSL https://get.docker.com | sh{RESET}
      {CYAN}sudo usermod -aG docker $USER && newgrp docker{RESET}

{BOLD}[3] Desenvolvimento sem Docker (temporário){RESET}
    Use a flag --dev-mode para rodar o agente no Windows sem isolamento.
    {YELLOW}⚠ NUNCA use em produção — apenas para testar o código!{RESET}
      {CYAN}python preflight_check.py --dev-mode{RESET}
      {CYAN}python main.py --task "sua tarefa"{RESET}
""")
    if plat["is_linux"] and not plat["is_wsl"]:
        print(f"""
{BOLD}[Linux — Docker Engine]{RESET}
    {CYAN}curl -fsSL https://get.docker.com | sh{RESET}
    {CYAN}sudo usermod -aG docker $USER && newgrp docker{RESET}

{BOLD}[Linux — KVM para Firecracker]{RESET}
    {CYAN}sudo apt install qemu-kvm{RESET}
    {CYAN}sudo usermod -aG kvm $USER{RESET}
    {CYAN}ls -la /dev/kvm{RESET}
""")
    print(f"""{BOLD}[VPS Linux — Deploy de Produção]{RESET}
    1. Verifique suporte KVM:
       {CYAN}grep -E 'vmx|svm' /proc/cpuinfo | head -1{RESET}
    2. Habilite Nested Virtualization no painel da VPS:
       • AWS: instâncias metal ou .xlarge c5/m5
       • Hetzner: CPX/CX (bare metal preferred)
       • DigitalOcean: Droplets dedicados
    3. Instale Firecracker:
       {CYAN}LATEST=$(curl -s https://api.github.com/repos/firecracker-microvm/firecracker/releases/latest | grep tag_name | cut -d'"' -f4){RESET}
       {CYAN}curl -LOJ https://github.com/firecracker-microvm/firecracker/releases/download/${{LATEST}}/firecracker-${{LATEST}}-x86_64.tgz{RESET}
    4. Validar na VPS:
       {CYAN}python preflight_check.py --strict{RESET}
""")


def run_checks(strict=False, dev_mode=False, fix_guide=False):
    critical_failures = []
    fix_needed = []
    plat = detect_platform()

    print(f"\n{BOLD}◈ KOSMOS Agent — Pre-Flight Security Check v2.2{RESET}")
    print(f"  {CYAN}Plataforma: {plat['system']} {plat['release']}", end="")
    if plat["is_mingw"]: print(f"  [Git Bash/MINGW]", end="")
    if plat["is_wsl"]:   print(f"  [WSL2]", end="")
    if dev_mode:         print(f"  {YELLOW}[DEV MODE ATIVO]{RESET}", end="")
    print(f"{RESET}")

    # ─── ISOLAMENTO DE EXECUÇÃO ───
    section("ISOLAMENTO DE EXECUÇÃO")

    kvm_ok, kvm_detail = check_kvm(plat)
    check("KVM disponível (/dev/kvm)", kvm_ok, warn_only=True, detail=kvm_detail)

    docker_ok, docker_detail = check_docker(plat)

    if not kvm_ok:
        _, dok = check(
            "Docker disponível (fallback seguro)",
            docker_ok,
            warn_only=dev_mode,
            detail=docker_detail if docker_ok else
                   docker_detail + " | Sem KVM nem Docker: execução BLOQUEADA [ATK-01]"
        )
        if not dok:
            if dev_mode:
                print(f"  {YELLOW}  [DEV] subprocess local permitido — SEM isolamento{RESET}")
                fix_needed.append("docker")
            else:
                critical_failures.append("Nenhum ambiente de execução isolado (KVM/Docker)")
                fix_needed.append("docker")

    if kvm_ok:
        print(f"  {INFO}  Firecracker MicroVM — modo produção completo")
    elif docker_ok:
        print(f"  {INFO}  Docker ativo — fallback seguro habilitado")
    elif dev_mode:
        print(f"  {YELLOW}  [DEV] Modo desenvolvimento — subprocess sem isolamento{RESET}")

    # ─── PATCHES DE SEGURANÇA ───
    section("PATCHES DE SEGURANÇA")
    base_dir = os.path.dirname(os.path.abspath(__file__))

    tr = os.path.join(base_dir, "tool_router.py")
    if os.path.exists(tr):
        c = open(tr, encoding="utf-8").read()
        lines = c.split("\n")
        sup_line = next((l for l in lines if "SUPPORTED_TOOLS" in l and "=" in l), "")
        unsafe_gone = "python_unsafe" not in sup_line
        check("[ATK-02] python_unsafe removido de SUPPORTED_TOOLS", unsafe_gone)
        if not unsafe_gone: critical_failures.append("[ATK-02] python_unsafe ainda em SUPPORTED_TOOLS")

        rp = "os.path.realpath" in c
        check("[ATK-03] os.path.realpath() — proteção symlink traversal", rp,
              detail="abspath é bypassável com symlinks")
        if not rp: critical_failures.append("[ATK-03] Symlink traversal não mitigado")
    else:
        check("tool_router.py encontrado", False, warn_only=True, detail=f"Esperado em: {tr}")

    sb = os.path.join(base_dir, "microvm_sandbox.py")
    if os.path.exists(sb):
        sc = open(sb, encoding="utf-8").read()
        check("[ATK-05] MAX_VSOCK_RESPONSE_SIZE — anti JSON Bomb", "MAX_VSOCK_RESPONSE_SIZE" in sc)
        if "MAX_VSOCK_RESPONSE_SIZE" not in sc:
            critical_failures.append("[ATK-05] Vsock JSON Bomb não mitigado")
        safe_fb = "_docker_execute" in sc or "Ambiente de execução isolado indisponível" in sc
        check("[ATK-01] Fallback seguro (Docker/Bloqueio) implementado", safe_fb,
              detail="Fallback NUNCA deve ser subprocess nu")
        if not safe_fb: critical_failures.append("[ATK-01] Fallback inseguro ainda presente")
    else:
        check("microvm_sandbox.py encontrado", False, warn_only=True)

    mem = os.path.join(base_dir, "memory.py")
    if os.path.exists(mem):
        mc = open(mem, encoding="utf-8").read()
        san = "SECRET_PATTERNS" in mc and "_sanitize_text" in mc
        check("[ATK-08] Sanitização de segredos na memória FAISS", san)
        if not san: critical_failures.append("[ATK-08] Memória FAISS vaza segredos")
    else:
        check("memory.py encontrado", False, warn_only=True)

    # ─── CONFIGURAÇÃO ───
    section("CONFIGURAÇÃO DE AMBIENTE")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    check("DEEPSEEK_API_KEY configurada", len(api_key) > 10, warn_only=True,
          detail="export DEEPSEEK_API_KEY=sk-... | Sem key: usa templates locais")

    gi_path = os.path.join(base_dir, ".gitignore")
    gi_ok = os.path.exists(gi_path) and ".env" in open(gi_path).read()
    check(".env no .gitignore", gi_ok, warn_only=True)

    # ─── DEPENDÊNCIAS ───
    section("DEPENDÊNCIAS")
    for pkg, imp, warn in [
        ("numpy", "numpy", False), ("requests", "requests", False),
        ("faiss-cpu", "faiss", True), ("jupyter_client", "jupyter_client", True),
    ]:
        try:
            __import__(imp); check(f"{pkg} instalado", True)
        except ImportError:
            check(f"{pkg} instalado", False, warn_only=warn,
                  detail=f"pip install {pkg}")
            if not warn: critical_failures.append(f"Dependência ausente: {pkg}")

    # ─── WORKSPACE ───
    section("WORKSPACE")
    workspace = os.path.join(base_dir, "workspace")
    check("Diretório workspace existe", os.path.isdir(workspace), detail=workspace)
    if os.path.isdir(workspace):
        real_ws = os.path.realpath(workspace)
        bad = []
        try:
            for e in os.scandir(workspace):
                if e.is_symlink():
                    t = os.path.realpath(e.path)
                    if not t.startswith(real_ws): bad.append(f"{e.name}→{t}")
        except PermissionError: pass
        check("Workspace sem symlinks suspeitos", not bad,
              detail=f"Suspeitos: {bad}" if bad else "")

    # ─── SUMÁRIO ───
    section("SUMÁRIO")

    if critical_failures:
        print(f"\n  {RED}{BOLD}✗ {len(critical_failures)} falha(s) crítica(s):{RESET}")
        for f in critical_failures:
            print(f"    {RED}• {f}{RESET}")
        if dev_mode:
            print(f"\n  {YELLOW}{BOLD}⚠ Dev Mode — iniciando com restrições de segurança.{RESET}")
            print(f"  {YELLOW}  Configure Docker antes do deploy em produção!{RESET}\n")
        else:
            print(f"\n  {RED}Sistema NÃO está pronto para produção.{RESET}")
            print(f"  Execute: {CYAN}python preflight_check.py --fix-guide{RESET} para instruções.\n")
        if fix_guide or fix_needed:
            print_fix_guide(plat, critical_failures)
        if strict and not dev_mode:
            sys.exit(1)
        return False
    else:
        print(f"\n  {GREEN}{BOLD}✓ Todos os checks críticos passaram!{RESET}")
        mode = "Firecracker MicroVM" if kvm_ok else "Docker (fallback seguro)"
        print(f"  {GREEN}  Modo de execução: {mode}{RESET}\n")
        return True


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="KOSMOS Pre-Flight Check v2.2")
    p.add_argument("--strict",     action="store_true", help="Exit 1 se falhar (CI/CD)")
    p.add_argument("--dev-mode",   action="store_true", help="Aceita Windows sem Docker (só dev!)")
    p.add_argument("--fix-guide",  action="store_true", help="Mostra guia de correção")
    args = p.parse_args()
    run_checks(strict=args.strict, dev_mode=args.dev_mode, fix_guide=args.fix_guide)
