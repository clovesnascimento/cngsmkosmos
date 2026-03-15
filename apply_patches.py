"""
apply_patches.py — KOSMOS Agent Windows Fix
============================================
Aplica TODOS os patches de compatibilidade Windows diretamente nos
arquivos do projeto. Execute uma vez na raiz do projeto.

Uso:
    cd D:\\FIRECRACKER\\kosmos_agent
    python apply_patches.py
"""

import os, sys, re, ast, shutil, platform

ROOT = os.path.dirname(os.path.abspath(__file__))

def backup(path):
    bak = path + ".bak2"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def validate(name, content):
    try:
        ast.parse(content)
        print(f"  ✓ {name} — parse OK")
        return True
    except SyntaxError as e:
        print(f"  ✗ {name} — SyntaxError: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════
# BLOCO DE COMPATIBILIDADE WINDOWS (injeta nos arquivos que precisam)
# ═══════════════════════════════════════════════════════════════════
COMPAT_RESOURCE = """\
# ── Windows Compatibility: resource/signal são Unix-only ──────────
import platform as _plat
_IS_WINDOWS = _plat.system() == "Windows"
if _IS_WINDOWS:
    import signal
    if not hasattr(signal, "SIGKILL"):
        signal.SIGKILL = signal.SIGTERM

    class _ResourceStub:
        RLIMIT_AS = 0; RLIMIT_CPU = 1; RLIMIT_DATA = 2
        def getrlimit(self, r): return (2**63, 2**63)
        def setrlimit(self, r, limits): pass
    resource = _ResourceStub()
else:
    import signal
    import resource
# ── End Windows Compatibility ──────────────────────────────────────
"""

COMPAT_RESOURCE_ONLY = """\
# ── Windows Compatibility: resource é Unix-only ───────────────────
import platform as _plat
_IS_WINDOWS = _plat.system() == "Windows"
if not _IS_WINDOWS:
    import resource
else:
    class _ResourceStub:
        RLIMIT_AS = 0; RLIMIT_CPU = 1; RLIMIT_DATA = 2
        def getrlimit(self, r): return (2**63, 2**63)
        def setrlimit(self, r, limits): pass
    resource = _ResourceStub()
# ── End Windows Compatibility ──────────────────────────────────────
"""

# ═══════════════════════════════════════════════
# Patch genérico: remove imports Unix e injeta shim
# ═══════════════════════════════════════════════
def patch_unix_imports(content, has_signal=False):
    """Remove bare unix imports e injeta bloco de compatibilidade."""
    if "Windows Compatibility" in content:
        return content, False  # já patchado

    modified = False

    if has_signal and "import signal" in content and "import resource" in content:
        # Remove ambos os imports simples
        content = re.sub(r'^import resource\s*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^import signal\s*\n', '', content, flags=re.MULTILINE)
        # Injeta após 'import tempfile' ou após os outros imports
        anchor = "import tempfile"
        if anchor in content:
            content = content.replace(anchor, anchor + "\n" + COMPAT_RESOURCE, 1)
        else:
            # Injeta após o primeiro bloco de imports
            content = re.sub(
                r'((?:^import \w+\s*\n|^from \w+ import .+\s*\n)+)',
                r'\1' + COMPAT_RESOURCE + '\n',
                content, count=1, flags=re.MULTILINE
            )
        modified = True

    elif "import resource" in content and not has_signal:
        content = re.sub(r'^import resource\s*\n', '', content, flags=re.MULTILINE)
        anchor = "import shutil"
        if anchor in content:
            content = content.replace(anchor, COMPAT_RESOURCE_ONLY + anchor, 1)
        else:
            content = re.sub(
                r'((?:^import \w+\s*\n|^from \w+ import .+\s*\n)+)',
                r'\1' + COMPAT_RESOURCE_ONLY + '\n',
                content, count=1, flags=re.MULTILINE
            )
        modified = True

    return content, modified

# ══════════════════════════════════
# PATCH ESPECÍFICO: microvm_sandbox
# ══════════════════════════════════
def patch_microvm_sandbox():
    path = os.path.join(ROOT, "microvm_sandbox.py")
    if not os.path.exists(path):
        print("  ⚠ microvm_sandbox.py não encontrado")
        return False

    backup(path)
    content = read(path)

    # 1. Fix imports Windows
    content, changed = patch_unix_imports(content, has_signal=True)
    if not changed and "Windows Compatibility" not in content:
        print("  ⚠ microvm_sandbox.py — imports não modificados")

    # 2. Fix docstring escape \p (SyntaxWarning)
    content = re.sub(
        r'"""Converte path Windows \(C:\\\\?path\).*?"""',
        '"""Converte path Windows para formato Docker Desktop (/c/path)."""',
        content
    )

    # 3. Garante que _windows_to_docker_path existe
    if "_windows_to_docker_path" not in content:
        converter = '''
    @staticmethod
    def _windows_to_docker_path(path: str) -> str:
        """Converte path Windows para formato Docker Desktop (/c/path)."""
        import platform
        if platform.system() != "Windows":
            return path
        path = path.replace("\\\\", "/")
        if len(path) >= 2 and path[1] == ":":
            path = "/" + path[0].lower() + path[2:]
        return path

'''
        content = content.replace("    def _docker_execute(", converter + "    def _docker_execute(", 1)

    # 4. Garante workspace montado no docker run
    if '"-v", f"{cwd}:/workspace:rw"' not in content and \
       '"-v", f"{self._windows_to_docker_path(cwd)}:/workspace:rw"' not in content:
        # Insere montagem do workspace antes do volume do código
        content = content.replace(
            '"-v", f"{tmp_path}:/code.py:ro"',
            '"-v", f"{self._windows_to_docker_path(cwd) if cwd else cwd}:/workspace:rw", "-w", "/workspace",\n'
            '                "-v", f"{self._windows_to_docker_path(tmp_path)}:/code.py:ro"'
        )
    elif '"-v", f"{tmp_path}:/code.py:ro"' in content:
        # Só atualiza para usar path converter
        content = content.replace(
            '"-v", f"{tmp_path}:/code.py:ro"',
            '"-v", f"{self._windows_to_docker_path(tmp_path)}:/code.py:ro"'
        )

    write(path, content)
    return validate("microvm_sandbox.py", content)

# ══════════════════════════════════
# PATCH ESPECÍFICO: tool_router
# ══════════════════════════════════
def patch_tool_router():
    path = os.path.join(ROOT, "tool_router.py")
    if not os.path.exists(path):
        print("  ⚠ tool_router.py não encontrado")
        return False

    backup(path)
    content = read(path)

    # 1. Fix imports Windows
    content, _ = patch_unix_imports(content, has_signal=False)

    # 2. Adiciona sanitizador de triple-quotes se não existir
    if "_sanitize_triple_quotes" not in content:
        sanitizer = '''
    @staticmethod
    def _sanitize_triple_quotes(code: str) -> str:
        """
        Reescreve triple-quoted strings em base64 para evitar SyntaxError
        quando o HTML/CSS gerado pelo LLM contém aspas simples/triplas.
        """
        import ast, re, base64 as _b64

        try:
            ast.parse(code)
            return code  # já válido
        except SyntaxError:
            pass

        logger.info("[Sanitizer] SyntaxError — convertendo triple-quotes para base64")

        def encode_block(m):
            varname = m.group(1)
            body    = m.group(2)
            enc = _b64.b64encode(body.encode("utf-8")).decode("ascii")
            return (
                f"{varname}__import__('base64').b64decode('{enc}').decode('utf-8')"
            )

        for q in ("\'\'\'", \'"""\'):
            pattern = re.compile(
                rf"([ \\t]*\\w+[ \\t]*=[ \\t]*){re.escape(q)}(.*?){re.escape(q)}",
                re.DOTALL
            )
            code = pattern.sub(encode_block, code)

        try:
            ast.parse(code)
            logger.info("[Sanitizer] Código sanitizado com sucesso")
        except SyntaxError as e:
            logger.warning(f"[Sanitizer] Fallback falhou ({e})")

        return code

'''
        content = content.replace(
            "    def _route_sandbox(",
            sanitizer + "    def _route_sandbox("
        )

    # 3. Garante que _route_sandbox chama o sanitizador
    if "_sanitize_triple_quotes" in content and \
       "_sanitize_triple_quotes(code)" not in content:
        content = content.replace(
            "    def _route_sandbox(self, code: str) -> Dict[str, Any]:\n"
            '        """MicroVM Firecracker — isolamento completo de hardware."""\n'
            "        logger.info(f\"→ MicroVM Sandbox [workspace={self.workspace_root}]\")\n"
            "        return self.sandbox.run(code, cwd=self.workspace_root)",

            "    def _route_sandbox(self, code: str) -> Dict[str, Any]:\n"
            '        """MicroVM Firecracker — isolamento completo de hardware."""\n'
            "        logger.info(f\"→ MicroVM Sandbox [workspace={self.workspace_root}]\")\n"
            "        code = self._sanitize_triple_quotes(code)\n"
            "        return self.sandbox.run(code, cwd=self.workspace_root)"
        )

    write(path, content)
    return validate("tool_router.py", content)

# ══════════════════════════════════
# MAIN
# ══════════════════════════════════
print()
print("◈ KOSMOS — Apply Windows Patches")
print("=" * 50)
print()

results = []

print("  [1/2] microvm_sandbox.py")
results.append(patch_microvm_sandbox())

print("  [2/2] tool_router.py")
results.append(patch_tool_router())

print()
print("=" * 50)
all_ok = all(results)

if all_ok:
    print("  ✓ Todos os patches aplicados com sucesso!")
    print()
    print("  Próximos passos:")
    print("    python preflight_check.py")
    print("    python kosmos_panel.py")
else:
    print("  ✗ Alguns patches falharam — verifique os erros acima")
    sys.exit(1)

print("=" * 50)
print()
