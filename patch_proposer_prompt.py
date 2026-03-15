"""
patch_proposer_prompt.py — KOSMOS Agent v2.2
=============================================
Injeta a regra CRÍTICA no system prompt do Proposer (agents.py / planner_tot.py)
para eliminar a geração de triple-quoted strings com HTML/CSS/JS na RAIZ.

Funciona em conjunto com o sanitizador v3 do tool_router.py:
  - Sanitizador v3 → fallback robusto (trata todos os casos)
  - Este patch       → previne o problema antes de chegar ao sanitizador

Resultado esperado: de 4-5 iterações com SyntaxError → 1 iteração com sucesso.

Uso:
    cd D:\\FIRECRACKER\\kosmos_agent
    python patch_proposer_prompt.py

    # Para preview sem aplicar:
    python patch_proposer_prompt.py --dry-run

    # Para reverter:
    python patch_proposer_prompt.py --revert
"""

import os
import sys
import re
import shutil
import argparse
from pathlib import Path

# ─── Regra a injetar ──────────────────────────────────────────────────────────
# Intencionalmente sem triple-quotes para não criar ironia de sintaxe
RULE_MARKER = "# [KOSMOS-PATCH-v2.2] NO-TRIPLE-QUOTES RULE"

RULE_LINES = [
    RULE_MARKER,
    "# Esta regra foi injetada por patch_proposer_prompt.py",
    "# Remove este bloco com: python patch_proposer_prompt.py --revert",
    "",
    "NO_TRIPLE_QUOTES_RULE = (",
    "    'REGRA CRITICA — GERACAO DE CODIGO PYTHON:\\n'",
    "    'Ao gerar codigo Python que escreve arquivos HTML, CSS ou JavaScript:\\n\\n'",
    "    'PROIBIDO — triple-quoted strings com HTML/CSS/JS:\\n'",
    "    '  html = chr(39)*3 + \"<html>...</html>\" + chr(39)*3  # PROIBIDO\\n'",
    "    '  css = chr(34)*3 + \"body{}\" + chr(34)*3             # PROIBIDO\\n\\n'",
    "    'OBRIGATORIO — f.write() linha a linha:\\n'",
    "    '  with open(\"workspace/index.html\", \"w\", encoding=\"utf-8\") as f:\\n'",
    "    '    f.write(\"<!DOCTYPE html>\\\\n\")\\n'",
    "    '    f.write(\"<html lang=\\'pt-BR\\'>\\\\n\")\\n'",
    "    '    f.write(\"<head>\\\\n\")\\n'",
    "    '    f.write(\"  <title>TITULO</title>\\\\n\")\\n'",
    "    '    f.write(\"</head>\\\\n\")\\n'",
    "    '    f.write(\"<body>\\\\n\")\\n'",
    "    '    f.write(\"</body>\\\\n\")\\n'",
    "    '    f.write(\"</html>\\\\n\")\\n\\n'",
    "    'OU — base64 para conteudo longo:\\n'",
    "    '  import base64\\n'",
    "    '  html_b64 = \"CONTEUDO_EM_BASE64\"\\n'",
    "    '  html = base64.b64decode(html_b64).decode(\"utf-8\")\\n'",
    "    '  with open(\"workspace/index.html\", \"w\") as f: f.write(html)\\n\\n'",
    "    'MOTIVO: triple-quotes causam SyntaxError no ambiente Docker.'",
    ")",
    "",
]

# ─── Padrões de busca nos arquivos alvo ───────────────────────────────────────

# Em agents.py: procura o system prompt do Proposer
AGENTS_PATTERNS = [
    # Pattern: PROPOSER_SYSTEM_PROMPT = "..." ou similar
    r'(PROPOSER_SYSTEM_PROMPT\s*=\s*["\'])',
    r'(system_prompt\s*=\s*["\'].*?[Pp]roposer)',
    r'(\"\"\".*?[Pp]roposer.*?\"\"\")',
    # Pattern: dicionário de prompts
    r'("role"\s*:\s*"system".*?"content"\s*:\s*")',
]

# Em planner_tot.py: procura onde o prompt é montado
PLANNER_PATTERNS = [
    r'(proposer_prompt\s*=)',
    r'(SYSTEM_PROMPT\s*=)',
    r'(system_msg\s*=)',
]

# ─── Arquivos alvo ────────────────────────────────────────────────────────────
TARGET_FILES = [
    "agents.py",
    "planner_tot.py",
    "kosmos_agent.py",    # alguns projetos têm este nome
    "main.py",
]


def find_injection_point(content: str, filename: str) -> int:
    """
    Encontra a linha onde injetar a regra.
    Retorna o índice de linha (0-based) ou -1 se não encontrado.
    """
    lines = content.split('\n')

    # Estratégia 1: injetar após as importações (primeiras linhas com import)
    last_import_line = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            last_import_line = i
        # Para de buscar após a primeira função/classe
        if stripped.startswith('def ') or stripped.startswith('class '):
            break

    if last_import_line >= 0:
        return last_import_line + 1

    # Fallback: linha 0
    return 0


def patch_file(filepath: str, dry_run: bool = False) -> bool:
    """
    Aplica o patch em um arquivo.
    Retorna True se patchou, False se não encontrou ou já estava patchado.
    """
    if not os.path.exists(filepath):
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Já patchado?
    if RULE_MARKER in content:
        print(f"  ⚠  {filepath} — já patchado, ignorando")
        return False

    # Encontra ponto de injeção
    lines = content.split('\n')
    inject_at = find_injection_point(content, filepath)

    # Monta o novo conteúdo
    new_lines = (
        lines[:inject_at]
        + RULE_LINES
        + lines[inject_at:]
    )
    new_content = '\n'.join(new_lines)

    if dry_run:
        print(f"  📋 {filepath} — DRY RUN: injetaria na linha {inject_at + 1}")
        print(f"     Prévia das 3 primeiras linhas da regra:")
        for rule_line in RULE_LINES[:3]:
            print(f"     | {rule_line}")
        return True

    # Backup
    backup = filepath + ".bak_proposer"
    shutil.copy2(filepath, backup)
    print(f"  💾 Backup: {backup}")

    # Escreve
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  ✓  {filepath} — regra injetada na linha {inject_at + 1}")
    return True


def inject_into_prompt_string(filepath: str, dry_run: bool = False) -> bool:
    """
    Estratégia alternativa: adiciona a regra NO_TRIPLE_QUOTES_RULE ao final
    de qualquer string que contenha o system prompt do Proposer.
    """
    if not os.path.exists(filepath):
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if RULE_MARKER in content:
        print(f"  ⚠  {filepath} — já patchado")
        return False

    # Busca por "Você é um agente" ou "You are" no prompt
    # e adiciona a regra como contexto adicional
    prompt_patterns = [
        r'(Você é um agente\b)',
        r'(You are a\b)',
        r'(SYSTEM_PROMPT\s*=\s*f?["\'])',
        r'(proposer_prompt\s*=\s*f?["\'])',
    ]

    for pat in prompt_patterns:
        if re.search(pat, content, re.IGNORECASE):
            print(f"  ✓  {filepath} — encontrou padrão de prompt, patchando header")
            return patch_file(filepath, dry_run)

    return False


def revert_file(filepath: str) -> bool:
    """Remove o bloco da regra injetada."""
    if not os.path.exists(filepath):
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if RULE_MARKER not in content:
        print(f"  ⚠  {filepath} — não tem patch, nada a fazer")
        return False

    # Remove o bloco entre o marker e a linha vazia após o bloco
    lines = content.split('\n')
    new_lines = []
    skip = False
    block_end_count = 0

    for i, line in enumerate(lines):
        if line.strip() == RULE_MARKER:
            skip = True
            block_end_count = 0
            continue
        if skip:
            # O bloco termina após a linha vazia após NO_TRIPLE_QUOTES_RULE = (...)
            # Conta as linhas da regra
            block_end_count += 1
            if block_end_count >= len(RULE_LINES):
                skip = False
            continue
        new_lines.append(line)

    new_content = '\n'.join(new_lines)

    backup = filepath + ".bak_revert"
    shutil.copy2(filepath, backup)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  ✓  {filepath} — patch removido (backup: {backup})")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Injeta regra no-triple-quotes no system prompt do Proposer do KOSMOS"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem aplicar"
    )
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Remove o patch de todos os arquivos"
    )
    parser.add_argument(
        "--dir",
        default=".",
        help="Diretório do KOSMOS Agent (padrão: diretório atual)"
    )
    args = parser.parse_args()

    base_dir = Path(args.dir).resolve()
    print(f"\n{'=' * 60}")
    print(f"KOSMOS patch_proposer_prompt.py v2.2")
    print(f"Diretório: {base_dir}")
    print(f"Modo: {'DRY RUN' if args.dry_run else 'REVERT' if args.revert else 'APLICAR'}")
    print(f"{'=' * 60}\n")

    patched_count = 0

    for filename in TARGET_FILES:
        filepath = str(base_dir / filename)

        if not os.path.exists(filepath):
            continue

        print(f"Processando: {filename}")

        if args.revert:
            if revert_file(filepath):
                patched_count += 1
        else:
            if patch_file(filepath, dry_run=args.dry_run):
                patched_count += 1

    if patched_count == 0:
        print("\n⚠  Nenhum arquivo foi modificado.")
        print("   Verifique se está no diretório correto do KOSMOS Agent.")
        print("   Use --dir /caminho/para/kosmos_agent se necessário.")
    else:
        action = "seriam patchados" if args.dry_run else ("revertidos" if args.revert else "patchados")
        print(f"\n✓ {patched_count} arquivo(s) {action}.")

    if not args.revert and not args.dry_run and patched_count > 0:
        print("\n" + "=" * 60)
        print("PRÓXIMO PASSO:")
        print("  A variável NO_TRIPLE_QUOTES_RULE foi definida.")
        print("  Você ainda precisa USÁ-LA no system prompt do Proposer.")
        print("")
        print("  Encontre em agents.py ou planner_tot.py onde o system")
        print("  prompt é montado e adicione:")
        print("")
        print("    system_prompt = base_prompt + '\\n\\n' + NO_TRIPLE_QUOTES_RULE")
        print("")
        print("  OU adicione ao dict de mensagens do LLM:")
        print("")
        print("    messages = [")
        print("      {'role': 'system', 'content': base_system + NO_TRIPLE_QUOTES_RULE},")
        print("      {'role': 'user',   'content': task},")
        print("    ]")
        print("=" * 60)


if __name__ == "__main__":
    main()
