"""
fix_windows_imports.py
======================
Corrige imports exclusivos Unix (resource, signal, fcntl) para rodar no Windows.
Execute na raiz do projeto: python fix_windows_imports.py
"""

import os
import re
import sys
import platform

# ── Verifica plataforma ──────────────────────────────────────────────────────
if platform.system() != "Windows":
    print("⚠ Este script é para Windows. No Linux/Mac os módulos já existem.")
    sys.exit(0)

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGETS = ["tool_router.py", "microvm_sandbox.py", "main.py", "kosmos_panel.py",
           "memory.py", "preflight_check.py", "jupyter_executor.py"]

# ── Bloco de compatibilidade que será injetado ───────────────────────────────
COMPAT_BLOCK = '''
# ── Windows Compatibility Shim ────────────────────────────────────────────────
import platform as _platform
_IS_WINDOWS = _platform.system() == "Windows"

if _IS_WINDOWS:
    # 'resource' não existe no Windows — stub com valores seguros
    class _ResourceStub:
        RLIMIT_AS   = 0
        RLIMIT_CPU  = 1
        RLIMIT_DATA = 2
        def getrlimit(self, r): return (2**63, 2**63)
        def setrlimit(self, r, limits): pass  # no-op no Windows
    resource = _ResourceStub()

    # 'signal.SIGKILL' não existe no Windows — usar SIGTERM
    import signal as _signal
    if not hasattr(_signal, "SIGKILL"):
        _signal.SIGKILL = _signal.SIGTERM
else:
    import resource
    import signal
# ── End Windows Shim ──────────────────────────────────────────────────────────
'''.strip()

# ── Padrões a substituir ─────────────────────────────────────────────────────
# Detecta linhas de import Unix-only simples no topo do arquivo
UNIX_IMPORTS = re.compile(
    r'^(import resource|from resource import .+)$', re.MULTILINE
)

SIGNAL_IMPORT = re.compile(
    r'^import signal$', re.MULTILINE
)

fixed = []
skipped = []

for fname in TARGETS:
    fpath = os.path.join(ROOT, fname)
    if not os.path.exists(fpath):
        skipped.append(fname)
        continue

    with open(fpath, "r", encoding="utf-8") as f:
        original = f.read()

    content = original

    # Checa se já foi patchado
    if "Windows Compatibility Shim" in content:
        print(f"  ✓ {fname} — já patchado, pulando")
        continue

    has_resource = bool(UNIX_IMPORTS.search(content))
    has_signal   = bool(SIGNAL_IMPORT.search(content))

    if not has_resource and not has_signal:
        skipped.append(fname)
        continue

    # Remove as linhas de import simples
    if has_resource:
        content = UNIX_IMPORTS.sub("", content)
    if has_signal:
        # Remove apenas se for import simples (não "from signal import ...")
        content = SIGNAL_IMPORT.sub("", content)

    # Injeta o bloco de compatibilidade logo após os imports padrão
    # Procura o fim do bloco de imports (primeira linha não-import, não-comentário)
    lines = content.split("\n")
    insert_at = 0
    in_docstring = False
    docstring_char = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Rastreia docstrings
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_char = stripped[:3]
                if stripped.count(docstring_char) >= 2 and len(stripped) > 3:
                    pass  # docstring de uma linha, continua
                else:
                    in_docstring = True
                continue
        else:
            if docstring_char in stripped:
                in_docstring = False
            continue

        # Linha de import → continua procurando
        if (stripped.startswith("import ") or
                stripped.startswith("from ") or
                stripped == "" or
                stripped.startswith("#")):
            insert_at = i + 1
            continue

        # Primeira linha de código real
        break

    lines.insert(insert_at, "\n" + COMPAT_BLOCK + "\n")
    content = "\n".join(lines)

    # Salva backup e escreve
    backup = fpath + ".bak"
    with open(backup, "w", encoding="utf-8") as f:
        f.write(original)

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)

    fixed.append(fname)
    print(f"  ✅ {fname} — patchado (backup em {fname}.bak)")

# ── Relatório ────────────────────────────────────────────────────────────────
print()
print("=" * 55)
print(f"  Arquivos patchados : {len(fixed)}")
print(f"  Arquivos pulados   : {len(skipped)}")
if fixed:
    print()
    print("  Próximo passo:")
    print("    python preflight_check.py")
    print("    python kosmos_panel.py")
print("=" * 55)
