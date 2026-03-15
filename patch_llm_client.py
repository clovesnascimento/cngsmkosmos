import sys, shutil, argparse
from pathlib import Path

TARGET = "llm_client.py"
MARKER = "# [KOSMOS-v2.3] SkillRouter integrado"

INJECTION = [
    '        # [KOSMOS-v2.3] SkillRouter integrado\n',
    '        _skill_protocol = ""\n',
    '        try:\n',
    '            from skill_router import SkillRouter\n',
    '            from skill_forge import SkillForge\n',
    '            if not hasattr(self, "_skill_router"):\n',
    '                self._skill_router = SkillRouter()\n',
    '                self._skill_forge  = SkillForge("skills_registry.json")\n',
    '            _skill_protocol = self._skill_router.route(task)\n',
    '            if not _skill_protocol:\n',
    '                forged = self._skill_forge.forge(task)\n',
    '                if forged:\n',
    '                    _skill_protocol = forged.protocol\n',
    '            if _skill_protocol:\n',
    '                import logging as _lg\n',
    '                _lg.getLogger("kosmos.llm").info(\n',
    '                    f"SkillRouter: protocolo injetado para \'{task[:40]}...\'"\n',
    '                )\n',
    '        except Exception as _e:\n',
    '            import logging as _lg\n',
    '            _lg.getLogger("kosmos.llm").warning(\n',
    '                f"SkillRouter: falhou ({_e}), usando base prompt"\n',
    '            )\n',
    '        _active_prompt = SYSTEM_PROMPT_PROPOSER + _skill_protocol\n',
]

def find_target_line(lines):
    """Encontra 'content = self.chat(' dentro de generate_proposal."""
    in_fn = False
    for i, line in enumerate(lines):
        if "def generate_proposal(" in line:
            in_fn = True
        if in_fn and "content = self.chat(" in line:
            return i
        if in_fn and i > 0 and line.strip().startswith("def ") and "generate_proposal" not in line:
            break
    return -1

def find_prompt_line(lines, start):
    """Encontra 'system_prompt=SYSTEM_PROMPT_PROPOSER,' apos start."""
    for i in range(start, min(start + 10, len(lines))):
        if "system_prompt=SYSTEM_PROMPT_PROPOSER," in lines[i]:
            return i
    return -1

def apply(dry_run=False):
    path = Path(TARGET)
    if not path.exists():
        print("ERRO: llm_client.py nao encontrado. Execute na pasta do KOSMOS.")
        sys.exit(1)
    content = path.read_text(encoding="utf-8")
    if MARKER in content:
        print("Patch ja aplicado. Use --revert para desfazer.")
        return
    lines = content.splitlines(keepends=True)

    # Linha do content = self.chat(
    chat_line = find_target_line(lines)
    if chat_line == -1:
        print("ERRO: 'content = self.chat(' nao encontrado em generate_proposal.")
        sys.exit(1)

    # Linha do system_prompt=SYSTEM_PROMPT_PROPOSER,
    prompt_line = find_prompt_line(lines, chat_line)
    if prompt_line == -1:
        print("ERRO: 'system_prompt=SYSTEM_PROMPT_PROPOSER,' nao encontrado.")
        sys.exit(1)

    if dry_run:
        print("DRY RUN OK")
        print(f"  Insere bloco antes da linha {chat_line+1}: {lines[chat_line].strip()}")
        print(f"  Troca linha {prompt_line+1}: {lines[prompt_line].strip()}")
        print(f"    SYSTEM_PROMPT_PROPOSER -> _active_prompt")
        return

    backup = TARGET + ".bak_skillrouter"
    shutil.copy2(TARGET, backup)
    print(f"Backup: {backup}")

    # Substitui system_prompt=SYSTEM_PROMPT_PROPOSER por _active_prompt
    lines[prompt_line] = lines[prompt_line].replace(
        "system_prompt=SYSTEM_PROMPT_PROPOSER,",
        "system_prompt=_active_prompt,"
    )

    # Insere o bloco ANTES de content = self.chat(
    new_lines = lines[:chat_line] + INJECTION + lines[chat_line:]
    path.write_text("".join(new_lines), encoding="utf-8")
    print(f"OK: {TARGET} patchado — SkillRouter ativo no Proposer")

def revert():
    backup = Path(TARGET + ".bak_skillrouter")
    if not backup.exists():
        print("ERRO: backup nao encontrado.")
        sys.exit(1)
    shutil.copy2(backup, TARGET)
    print(f"OK: {TARGET} revertido")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--revert",  action="store_true")
    args = p.parse_args()
    revert() if args.revert else apply(args.dry_run)
