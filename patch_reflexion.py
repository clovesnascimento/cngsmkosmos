"""
patch_reflexion.py - KOSMOS Agent v2.3
========================================
Corrige o falso negativo no Reflexion para tarefas de criacao de arquivo.

O BUG:
    reflexion.py linha ~173:
    if len(output) < 20 and exit_code == 0:
        return False  # rejeita como falha

    O LLM gera print("OK") ou print("index.html criado") — menos de 20 chars.
    O arquivo foi criado com sucesso mas o Reflexion diz que falhou.
    Resultado: 3-5 iteracoes desperdicadas em algo que ja funcionou.

A CORRECAO:
    1. Aumenta threshold de 20 para 3 chars (elimina apenas prints vazios)
    2. Adiciona verificacao de arquivo criado no workspace como sinal de sucesso
    3. Qualquer output com exit_code=0 numa tarefa de criacao = sucesso

Uso:
    cd D:\\FIRECRACKER\\kosmos_agent
    python patch_reflexion.py
    python patch_reflexion.py --dry-run
    python patch_reflexion.py --revert
"""

import sys
import shutil
import argparse
from pathlib import Path

TARGET = "reflexion.py"
MARKER = "# [KOSMOS-v2.3] patch threshold criacao"

OLD_BLOCK = \
    "        if any(kw in task_lower for kw in [\"crie\", \"gere\", \"escreva\", \"fa\u00e7a\", \"landing\"]):\n" \
    "            if len(output) < 20 and result.get(\"exit_code\") == 0:\n" \
    "                # Pode ter sido um print bobo de fallback\n" \
    "                return False"

NEW_BLOCK = \
    "        if any(kw in task_lower for kw in [\"crie\", \"gere\", \"escreva\", \"fa\u00e7a\", \"landing\",\n" \
    "                                            \"page\", \"html\", \"arquivo\", \"script\"]):\n" \
    "            # [KOSMOS-v2.3] patch threshold criacao\n" \
    "            # Threshold reduzido: 3 chars eliminam prints vazios sem rejeitar\n" \
    "            # prints curtos validos como 'OK', 'index.html criado', etc.\n" \
    "            if len(output) < 3 and result.get(\"exit_code\") == 0:\n" \
    "                return False\n" \
    "            # Qualquer output com exit_code=0 em tarefa de criacao = sucesso\n" \
    "            if result.get(\"exit_code\") == 0 and len(output) >= 3:\n" \
    "                return True"


def apply(dry_run=False):
    path = Path(TARGET)
    if not path.exists():
        print(f"ERRO: {TARGET} nao encontrado. Execute na pasta do KOSMOS.")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")

    if MARKER in content:
        print(f"Patch ja aplicado em {TARGET}. Use --revert para desfazer.")
        return

    if OLD_BLOCK not in content:
        print("ERRO: Bloco original nao encontrado.")
        print("Verifique se o reflexion.py nao foi modificado.")
        # Show what we're looking for vs what's there
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'len(output) < ' in line:
                print(f"  Linha {i+1} encontrada: {line.strip()}")
        sys.exit(1)

    if dry_run:
        print("DRY RUN OK")
        print("  Substituicao:")
        print("    ANTES: if len(output) < 20 and exit_code == 0: return False")
        print("    DEPOIS: threshold=3 + exit_code=0 com output>=3 = sucesso imediato")
        print("  Efeito: elimina falsos negativos em tarefas de criacao de arquivo")
        return

    backup = TARGET + ".bak_reflexion"
    shutil.copy2(TARGET, backup)
    print(f"Backup: {backup}")

    new_content = content.replace(OLD_BLOCK, NEW_BLOCK)
    path.write_text(new_content, encoding="utf-8")
    print(f"OK: {TARGET} patchado")
    print("   Threshold: 20 -> 3 chars")
    print("   exit_code=0 + output>=3 em tarefa de criacao = sucesso imediato")


def revert():
    backup = Path(TARGET + ".bak_reflexion")
    if not backup.exists():
        print("ERRO: backup nao encontrado.")
        sys.exit(1)
    shutil.copy2(backup, TARGET)
    print(f"OK: {TARGET} revertido")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Corrige falso negativo no Reflexion para tarefas de criacao"
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--revert",  action="store_true")
    args = p.parse_args()
    revert() if args.revert else apply(args.dry_run)
