"""
patch_anthropic_sdk.py - KOSMOS Agent v2.4
==========================================
Dois patches em um:

1. MIGRA para Anthropic SDK com DeepSeek
   - Troca requests.post por anthropic.Anthropic()
   - Usa ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
   - Melhor handling de respostas longas e timeouts

2. CORRIGE _parse_json_response
   - Suporta campo 'content' com HTML bruto
   - Suporta tool=write_file diretamente no JSON
   - Extrai HTML mesmo quando o JSON esta quebrado

Uso:
    cd D:\\FIRECRACKER\\kosmos_agent
    pip install anthropic
    python patch_anthropic_sdk.py
    python patch_anthropic_sdk.py --dry-run
    python patch_anthropic_sdk.py --revert
"""

import sys
import shutil
import argparse
from pathlib import Path

TARGET = "llm_client.py"
MARKER = "# [KOSMOS-v2.4] Anthropic SDK"


def find_line(lines, text, start=0):
    for i in range(start, len(lines)):
        if text in lines[i]:
            return i
    return -1


def apply(dry_run=False):
    path = Path(TARGET)
    if not path.exists():
        print(f"ERRO: {TARGET} nao encontrado.")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")

    if MARKER in content:
        print("Patch ja aplicado. Use --revert para desfazer.")
        return

    lines = content.splitlines(keepends=True)

    # ── PATCH 1: Adiciona import anthropic e configura env vars ──────
    # Encontra o bloco de imports (apos os imports existentes)
    last_import = -1
    for i, line in enumerate(lines[:20]):
        if line.startswith("import ") or line.startswith("from "):
            last_import = i

    new_imports = [
        "\n",
        "# [KOSMOS-v2.4] Anthropic SDK — DeepSeek via Anthropic API\n",
        "import os as _os_sdk\n",
        "_os_sdk.environ.setdefault('ANTHROPIC_BASE_URL', 'https://api.deepseek.com/anthropic')\n",
        "# ANTHROPIC_API_KEY sera lido do DEEPSEEK_API_KEY automaticamente\n",
        "if not _os_sdk.environ.get('ANTHROPIC_API_KEY'):\n",
        "    _deepseek_key = _os_sdk.environ.get('DEEPSEEK_API_KEY', '')\n",
        "    if _deepseek_key:\n",
        "        _os_sdk.environ['ANTHROPIC_API_KEY'] = _deepseek_key\n",
        "try:\n",
        "    import anthropic as _anthropic_sdk\n",
        "    _ANTHROPIC_AVAILABLE = True\n",
        "except ImportError:\n",
        "    _ANTHROPIC_AVAILABLE = False\n",
        "\n",
    ]

    # ── PATCH 2: Substitui _make_request para usar Anthropic SDK ─────
    # Encontra inicio do _make_request
    make_req_start = find_line(lines, "def _make_request(")
    make_req_end = find_line(lines, "def _parse_json_response(")

    if make_req_start == -1 or make_req_end == -1:
        print("ERRO: _make_request ou _parse_json_response nao encontrados")
        sys.exit(1)

    new_make_request = [
        "    def _make_request(\n",
        "        self,\n",
        "        messages: List[Dict[str, str]],\n",
        "        model: Optional[str] = None,\n",
        "        temperature: Optional[float] = None,\n",
        "        max_tokens: Optional[int] = None,\n",
        "    ) -> Dict[str, Any]:\n",
        "        # [KOSMOS-v2.4] Anthropic SDK — usa DeepSeek via Anthropic API\n",
        "        _model = model or self.config.model\n",
        "        _temp = temperature or self.config.temperature\n",
        "        _max_tokens = max_tokens or self.config.max_tokens\n",
        "\n",
        "        # Separa system prompt das mensagens\n",
        "        system_msg = None\n",
        "        user_msgs = []\n",
        "        for m in messages:\n",
        "            if m.get('role') == 'system':\n",
        "                system_msg = m['content']\n",
        "            else:\n",
        "                user_msgs.append(m)\n",
        "\n",
        "        if not user_msgs:\n",
        "            return {'raw': ''}\n",
        "\n",
        "        for attempt in range(self.config.retry_count):\n",
        "            try:\n",
        "                if _ANTHROPIC_AVAILABLE:\n",
        "                    logger.info(f'Chamando DeepSeek API ({len(messages)} mensagens)...')\n",
        "                    client = _anthropic_sdk.Anthropic()\n",
        "                    kwargs = dict(\n",
        "                        model='deepseek-chat',\n",
        "                        max_tokens=_max_tokens,\n",
        "                        messages=user_msgs,\n",
        "                        temperature=_temp,\n",
        "                    )\n",
        "                    if system_msg:\n",
        "                        kwargs['system'] = system_msg\n",
        "                    response = client.messages.create(**kwargs)\n",
        "                    logger.info(f'Resposta recebida da DeepSeek API (status=200)')\n",
        "                    self._request_count += 1\n",
        "                    text = response.content[0].text if response.content else ''\n",
        "                    self._total_tokens += (response.usage.input_tokens + response.usage.output_tokens)\n",
        "                    logger.debug(f'API call #{self._request_count}: tokens={response.usage.input_tokens + response.usage.output_tokens}')\n",
        "                    return {'raw': text}\n",
        "                else:\n",
        "                    # Fallback para requests (OpenAI-compatible)\n",
        "                    import requests\n",
        "                    base = self.config.api_base.rstrip('/')\n",
        "                    url = f'{base}/v1/chat/completions' if '/v1' not in base else f'{base}/chat/completions'\n",
        "                    headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}\n",
        "                    payload = {'model': _model, 'messages': messages, 'temperature': _temp, 'max_tokens': _max_tokens, 'stream': False}\n",
        "                    logger.info(f'Chamando DeepSeek API ({len(messages)} mensagens)...')\n",
        "                    r = requests.post(url, headers=headers, json=payload, timeout=self.config.timeout)\n",
        "                    logger.info(f'Resposta recebida da DeepSeek API (status={r.status_code})')\n",
        "                    if r.status_code == 200:\n",
        "                        data = r.json()\n",
        "                        self._total_tokens += data.get('usage', {}).get('total_tokens', 0)\n",
        "                        self._request_count += 1\n",
        "                        return {'raw': data['choices'][0]['message']['content']}\n",
        "                    else:\n",
        "                        logger.error(f'API error: {r.status_code} {r.text[:200]}')\n",
        "            except Exception as e:\n",
        "                logger.warning(f'Tentativa {attempt+1} falhou: {e}')\n",
        "                if attempt < self.config.retry_count - 1:\n",
        "                    import time\n",
        "                    time.sleep(2 ** attempt)\n",
        "        return {'raw': ''}\n",
        "\n",
    ]

    # ── PATCH 3: Corrige _parse_json_response ─────────────────────────
    parse_start = make_req_end
    # Encontra o fim do _parse_json_response (proxima def)
    parse_end = find_line(lines, "    def ", parse_start + 1)

    new_parse = [
        "    def _parse_json_response(self, content: str) -> Dict[str, Any]:\n",
        "        \"\"\"\n",
        "        [KOSMOS-v2.4] Parser robusto — suporta:\n",
        "          - JSON normal com campo 'code'\n",
        "          - JSON com tool=write_file e campo 'content' (HTML bruto)\n",
        "          - JSON quebrado por HTML com aspas\n",
        "          - Extrai HTML mesmo quando JSON invalido\n",
        "        \"\"\"\n",
        "        content = content.strip()\n",
        "\n",
        "        # Tenta parse normal primeiro\n",
        "        parsed = self._extract_json(content)\n",
        "        if parsed is not None:\n",
        "            # Se tem tool=write_file com content, retorna direto\n",
        "            if parsed.get('tool') == 'write_file' and parsed.get('content'):\n",
        "                return parsed\n",
        "            # Se tem code, retorna normal\n",
        "            if parsed.get('code'):\n",
        "                return parsed\n",
        "\n",
        "        # JSON quebrado — tenta extrair campos individualmente\n",
        "        import re\n",
        "        result = {}\n",
        "\n",
        "        # Extrai thought\n",
        "        m = re.search(r'\"thought\"\\s*:\\s*\"(.*?)\"(?=\\s*,\\s*\"(?:tool|code|strategy)\")', content, re.DOTALL)\n",
        "        if m:\n",
        "            result['thought'] = m.group(1)\n",
        "\n",
        "        # Detecta se e write_file\n",
        "        if '\"tool\"' in content and 'write_file' in content:\n",
        "            result['tool'] = 'write_file'\n",
        "            # Extrai path\n",
        "            pm = re.search(r'\"path\"\\s*:\\s*\"([^\"]+)\"', content)\n",
        "            if pm:\n",
        "                result['path'] = pm.group(1)\n",
        "            # Extrai content — tudo entre 'content': \" e o ultimo \"\n",
        "            cm = re.search(r'\"content\"\\s*:\\s*\"(.*)', content, re.DOTALL)\n",
        "            if cm:\n",
        "                html = cm.group(1)\n",
        "                # Remove trailing JSON artifacts\n",
        "                if html.endswith('\"}'): html = html[:-2]\n",
        "                elif html.endswith('\"'): html = html[:-1]\n",
        "                result['content'] = html\n",
        "                result['strategy'] = 'write_file'\n",
        "                return result\n",
        "\n",
        "        # Detecta bloco de codigo Python\n",
        "        code_m = re.search(r'\"code\"\\s*:\\s*\"(.*?)\"(?=\\s*[,}])', content, re.DOTALL)\n",
        "        if code_m:\n",
        "            result['code'] = code_m.group(1).replace('\\\\n', '\\n').replace('\\\\t', '\\t')\n",
        "            sm = re.search(r'\"strategy\"\\s*:\\s*\"([^\"]+)\"', content)\n",
        "            result['strategy'] = sm.group(1) if sm else 'llm_generated'\n",
        "            return result\n",
        "\n",
        "        logger.warning(f'Falha ao parsear JSON: {content[:200]}')\n",
        "        return {'raw': content}\n",
        "\n",
    ]

    if dry_run:
        print("DRY RUN OK")
        print(f"  PATCH 1: inject Anthropic SDK setup apos linha {last_import+1}")
        print(f"  PATCH 2: substituir _make_request (linhas {make_req_start+1}-{make_req_end})")
        print(f"  PATCH 3: substituir _parse_json_response (linhas {parse_start+1}-{parse_end})")
        print(f"  Efeito: DeepSeek via Anthropic SDK + parser robusto write_file")
        return

    backup = TARGET + ".bak_anthropic"
    shutil.copy2(TARGET, backup)
    print(f"Backup: {backup}")

    # Aplica os patches
    new_lines = (
        lines[:last_import + 1] +
        new_imports +
        lines[last_import + 1:make_req_start] +
        new_make_request +
        new_parse +
        lines[parse_end:]
    )

    path.write_text("".join(new_lines), encoding="utf-8")
    print(f"OK: {TARGET} patchado — Anthropic SDK + parser write_file")


def revert():
    backup = Path(TARGET + ".bak_anthropic")
    if not backup.exists():
        print("ERRO: backup nao encontrado.")
        sys.exit(1)
    shutil.copy2(backup, TARGET)
    print(f"OK: {TARGET} revertido")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--revert", action="store_true")
    args = p.parse_args()
    revert() if args.revert else apply(args.dry_run)
