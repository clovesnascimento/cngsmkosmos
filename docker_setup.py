"""
docker_setup.py
===============
Pré-requisito do KOSMOS Agent no Windows com Docker fallback.
Executa UMA VEZ para preparar o ambiente Docker.

Uso: python docker_setup.py
"""

import subprocess
import sys
import os
import tempfile

IMAGE = "python:3.11-slim"

def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

def banner(msg):
    print(f"\n  {'─'*50}")
    print(f"  {msg}")
    print(f"  {'─'*50}")

# ── 1. Verifica Docker ───────────────────────────────────
banner("1/4 — Verificando Docker")
r = run(["docker", "info"])
if r.returncode != 0:
    print("  ✗ Docker não está rodando. Inicie o Docker Desktop e tente novamente.")
    sys.exit(1)
print("  ✓ Docker daemon ativo")

# ── 2. Verifica se imagem já existe ─────────────────────
banner("2/4 — Verificando imagem python:3.11-slim")
r = run(["docker", "image", "inspect", IMAGE])
if r.returncode == 0:
    print(f"  ✓ Imagem {IMAGE} já está em cache — nenhum download necessário")
else:
    print(f"  ⬇ Fazendo pull de {IMAGE} (só acontece uma vez)...")
    print("    Isso pode levar 1-2 minutos dependendo da conexão...\n")
    result = subprocess.run(["docker", "pull", IMAGE])
    if result.returncode != 0:
        print(f"\n  ✗ Falha ao baixar {IMAGE}")
        sys.exit(1)
    print(f"\n  ✓ {IMAGE} baixado com sucesso")

# ── 3. Testa execução + escrita de arquivo ───────────────
banner("3/4 — Testando execução Docker com workspace")

workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace")
os.makedirs(workspace, exist_ok=True)

test_code = """
import os, sys
print(f"Python {sys.version}")
print(f"CWD: {os.getcwd()}")

# Testa escrita de arquivo no workspace montado
with open('/workspace/docker_test.txt', 'w') as f:
    f.write('Docker workspace mount OK!')
print("Arquivo escrito: /workspace/docker_test.txt")
"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
    f.write(test_code)
    tmp = f.name

# Windows path para Docker (converter \ para /)
workspace_docker = workspace.replace("\\", "/")
if workspace_docker[1] == ":":
    # C:\path → /c/path  (formato MINGW/Docker Desktop)
    workspace_docker = "/" + workspace_docker[0].lower() + workspace_docker[2:]

tmp_docker = tmp.replace("\\", "/")
if tmp_docker[1] == ":":
    tmp_docker = "/" + tmp_docker[0].lower() + tmp_docker[2:]

cmd = [
    "docker", "run", "--rm",
    "--network", "none",
    "--memory", "256m",
    "--cpus", "1.0",
    "--security-opt", "no-new-privileges",
    "-v", f"{tmp_docker}:/code.py:ro",
    "-v", f"{workspace_docker}:/workspace:rw",
    "-w", "/workspace",
    IMAGE,
    "python", "/code.py"
]

result = subprocess.run(cmd, capture_output=True, text=True)
os.remove(tmp)

if result.returncode == 0:
    print("  ✓ Container executou com sucesso:")
    for line in result.stdout.strip().split('\n'):
        print(f"    {line}")
    
    test_file = os.path.join(workspace, "docker_test.txt")
    if os.path.exists(test_file):
        print("  ✓ Workspace mount funcionando — arquivo persistido no host")
        os.remove(test_file)
    else:
        print("  ⚠ Workspace mount pode não estar funcionando (verifique paths)")
else:
    print("  ✗ Erro na execução Docker:")
    print(result.stderr[:500])

# ── 4. Atualiza microvm_sandbox.py com path converter ────
banner("4/4 — Verificando path converter Windows→Docker")

sandbox_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "microvm_sandbox.py")
if os.path.exists(sandbox_path):
    with open(sandbox_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '_windows_to_docker_path' in content:
        print("  ✓ Path converter já está instalado")
    else:
        print("  ℹ Path converter não encontrado — aplicando patch...")
        # Injeta helper de conversão de path Windows→Docker antes do _docker_execute
        patch = '''
    @staticmethod
    def _windows_to_docker_path(path: str) -> str:
        """Converte path Windows (C:\\path) para formato Docker Desktop (//c/path)."""
        import platform
        if platform.system() != "Windows":
            return path
        path = path.replace("\\\\", "/")
        if len(path) >= 2 and path[1] == ":":
            path = "/" + path[0].lower() + path[2:]
        return path

'''
        content = content.replace(
            "    def _docker_execute(",
            patch + "    def _docker_execute("
        )

        # Atualiza os volumes para usar o converter
        content = content.replace(
            '"-v", f"{tmp_path}:/code.py:ro", # Código como read-only',
            '"-v", f"{self._windows_to_docker_path(tmp_path)}:/code.py:ro",'
        )
        content = content.replace(
            '"-v", f"{cwd}:/workspace:rw", "-w", "/workspace"',
            '"-v", f"{self._windows_to_docker_path(cwd)}:/workspace:rw", "-w", "/workspace"'
        )

        with open(sandbox_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("  ✓ Path converter instalado em microvm_sandbox.py")
else:
    print(f"  ⚠ microvm_sandbox.py não encontrado em {sandbox_path}")

# ── Resumo ───────────────────────────────────────────────
print(f"""
  {'='*52}
  ✓ Docker setup completo!

  Próximos passos:
    python preflight_check.py
    python kosmos_panel.py

  Nota: a imagem {IMAGE} está em cache.
  Execuções futuras serão instantâneas (~2s boot).
  {'='*52}
""")
