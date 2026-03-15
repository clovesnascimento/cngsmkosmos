"""
kosmos_parser.py — KOSMOS Stage 2 Solution
===========================================
F4 — Parser robusto com 6 estratégias de fallback:
    S1: json.loads direto
    S2: extrai bloco ```json...```
    S3: balanceamento de chaves
    S4: extração de campos por regex
    S5: repair de JSON truncado
    S6: extração de HTML/content de write_file quebrado

F5 — Compressor dinâmico de prompt:
    - Remove linhas duplicadas
    - Colapsa exemplos verbose em referências compactas
    - Preserva seções marcadas como críticas (PROIBIDO, OBRIGATÓRIO, NUNCA)
    - Trunca seções de baixa prioridade quando acima do limite
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("kosmos.parser")


# ══════════════════════════════════════════════════════════════════
# ROBUST PARSER
# ══════════════════════════════════════════════════════════════════

class RobustParser:
    """
    Parser JSON com 6 estratégias de fallback.
    Nunca lança exceção — sempre retorna um dict.
    """

    def parse(self, text: str) -> Dict[str, Any]:
        """
        Tenta extrair JSON usando 6 estratégias em ordem crescente de agressividade.
        Retorna o primeiro resultado válido.
        """
        if not text or not text.strip():
            return {"raw": ""}

        text = text.strip()

        # S1: JSON direto
        result = self._s1_direct(text)
        if self._is_valid(result):
            logger.debug("Parser: S1 (direto)")
            return result

        # S2: Bloco markdown ```json ... ```
        result = self._s2_markdown(text)
        if self._is_valid(result):
            logger.debug("Parser: S2 (markdown)")
            return result

        # S3: Balanceamento de chaves
        result = self._s3_balanced(text)
        if self._is_valid(result):
            logger.debug("Parser: S3 (balanceado)")
            return result

        # S4: Repair de JSON (aspas não escapadas, newlines literais)
        result = self._s4_repair(text)
        if self._is_valid(result):
            logger.debug("Parser: S4 (repair)")
            return result

        # S5: Extração de campos por regex
        result = self._s5_regex(text)
        if self._is_valid(result):
            logger.debug("Parser: S5 (regex)")
            return result

        # S6: Extração especial para write_file com HTML
        result = self._s6_write_file(text)
        if result.get("tool") == "write_file":
            logger.debug("Parser: S6 (write_file)")
            return result

        logger.warning(f"Parser: todas as estratégias falharam para: {text[:100]}...")
        return {"raw": text}

    # ── Estratégia 1: JSON direto ─────────────────────────────────

    def _s1_direct(self, text: str) -> Optional[Dict]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # ── Estratégia 2: Bloco markdown ─────────────────────────────

    def _s2_markdown(self, text: str) -> Optional[Dict]:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    # ── Estratégia 3: Balanceamento de chaves ─────────────────────

    def _s3_balanced(self, text: str) -> Optional[Dict]:
        start = text.find("{")
        if start == -1:
            return None

        json_part = text[start:]
        stack = []
        in_string = False
        escape = False
        last_close = -1

        for i, ch in enumerate(json_part):
            if ch == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if ch == "{":
                    stack.append("}")
                elif ch == "[":
                    stack.append("]")
                elif ch in "}]":
                    if stack and ch == stack[-1]:
                        stack.pop()
                        if not stack:
                            last_close = i + 1
                            break
            escape = (ch == "\\" and not escape)

        if last_close > 0:
            try:
                return json.loads(json_part[:last_close])
            except json.JSONDecodeError:
                pass
        return None

    # ── Estratégia 4: Repair de JSON ─────────────────────────────

    def _s4_repair(self, text: str) -> Optional[Dict]:
        """
        Tenta reparar JSON com problemas comuns:
        - Newlines literais dentro de strings
        - Aspas não escapadas
        - Truncamento no final
        """
        start = text.find("{")
        if start == -1:
            return None

        repaired = text[start:]

        # Fix newlines literais dentro de strings
        repaired = self._fix_literal_newlines(repaired)

        # Fix JSON truncado: adiciona fechamento se necessário
        repaired = self._close_truncated(repaired)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        return None

    def _fix_literal_newlines(self, text: str) -> str:
        """Substitui newlines literais dentro de strings JSON por \\n."""
        result = []
        in_string = False
        escape = False
        i = 0

        while i < len(text):
            ch = text[i]
            if ch == '"' and not escape:
                in_string = not in_string
                result.append(ch)
            elif in_string and ch == '\n' and not escape:
                result.append('\\n')
            elif in_string and ch == '\r' and not escape:
                result.append('\\r')
            elif in_string and ch == '\t' and not escape:
                result.append('\\t')
            else:
                result.append(ch)
            escape = (ch == '\\' and not escape and in_string)
            i += 1

        return ''.join(result)

    def _close_truncated(self, text: str) -> str:
        """Fecha JSON truncado adicionando aspas e chaves faltantes."""
        text = text.rstrip()

        # Conta chaves abertas
        stack = []
        in_string = False
        escape = False

        for ch in text:
            if ch == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if ch in "{[":
                    stack.append("}" if ch == "{" else "]")
                elif ch in "}]":
                    if stack:
                        stack.pop()
            escape = (ch == "\\" and not escape)

        # Se estava dentro de string, fecha
        if in_string:
            text += '"'

        # Fecha estruturas abertas
        while stack:
            text += stack.pop()

        return text

    # ── Estratégia 5: Extração por regex ─────────────────────────

    def _s5_regex(self, text: str) -> Dict[str, Any]:
        """Extrai campos individualmente via regex."""
        result = {}

        # thought
        m = re.search(r'"thought"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            result["thought"] = m.group(1).replace('\\"', '"')

        # strategy
        m = re.search(r'"strategy"\s*:\s*"([^"]+)"', text)
        if m:
            result["strategy"] = m.group(1)

        # tool
        m = re.search(r'"tool"\s*:\s*"([^"]+)"', text)
        if m:
            result["tool"] = m.group(1)

        # path
        m = re.search(r'"path"\s*:\s*"([^"]+)"', text)
        if m:
            result["path"] = m.group(1)

        # code — captura até o próximo campo ou fim
        m = re.search(
            r'"code"\s*:\s*"(.*?)(?="(?:\s*[,}]|\s*$)|\Z)',
            text, re.DOTALL
        )
        if m:
            code = m.group(1)
            code = code.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
            result["code"] = code

        return result

    # ── Estratégia 6: write_file especial ────────────────────────

    def _s6_write_file(self, text: str) -> Dict[str, Any]:
        """
        Extração especial para write_file com HTML que quebra o JSON.
        Busca o padrão: "tool": "write_file" + "content": "..."
        """
        result = {"tool": "write_file"}

        # Extrai path
        m = re.search(r'"path"\s*:\s*"([^"]+)"', text)
        result["path"] = m.group(1) if m else "index.html"

        # Extrai strategy
        m = re.search(r'"strategy"\s*:\s*"([^"]+)"', text)
        result["strategy"] = m.group(1) if m else "write_file"

        # Extrai thought
        m = re.search(r'"thought"\s*:\s*"(.*?)"(?=\s*,\s*"(?:tool|path|content|strategy)")', text, re.DOTALL)
        if m:
            result["thought"] = m.group(1)

        # Extrai content — tudo após "content": "
        m = re.search(r'"content"\s*:\s*"(.*)', text, re.DOTALL)
        if m:
            content = m.group(1)
            # Remove sufixo JSON
            for suffix in ['"}', '"}\n', '" }', '" }\n']:
                if content.endswith(suffix):
                    content = content[:-len(suffix)]
                    break
            if content.endswith('"'):
                content = content[:-1]
            # Desescapa
            content = content.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
            result["content"] = content

        return result if result.get("content") else {}

    # ── Validação ─────────────────────────────────────────────────

    def _is_valid(self, result: Optional[Dict]) -> bool:
        """Um resultado é válido se tem code ou (tool=write_file + content)."""
        if not result or not isinstance(result, dict):
            return False
        if result.get("code"):
            return True
        if result.get("tool") == "write_file" and result.get("content"):
            return True
        return False


# ══════════════════════════════════════════════════════════════════
# PROMPT COMPRESSOR
# ══════════════════════════════════════════════════════════════════

class PromptCompressor:
    """
    Compressor dinâmico de prompt que:
    1. Remove linhas duplicadas
    2. Colapsa exemplos verbose
    3. Preserva seções críticas (PROIBIDO, OBRIGATÓRIO, NUNCA, FASE 1/2)
    4. Trunca seções de baixa prioridade
    """

    # Palavras que indicam linha crítica — nunca remover
    CRITICAL_MARKERS = [
        "PROIBIDO", "OBRIGATÓRIO", "OBRIGATORIO", "NUNCA",
        "FASE 1", "FASE 2", "REGRA ABSOLUTA", "REGRA CRÍTICA",
        "JAMAIS", "SEMPRE", "NEVER", "MUST",
    ]

    # Padrões de exemplo verbose que podem ser colapsados
    VERBOSE_PATTERNS = [
        r'(Ex:|Exemplo:|Example:).*\n(.*\n){0,3}',   # exemplos com continuação
        r'```python\n(.*\n){3,}```',                   # blocos de código longos
        r'([\s]*#.*\n){3,}',                           # sequências de comentários
    ]

    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens

    def compress(self, prompt: str) -> str:
        """
        Comprime o prompt para dentro do limite de tokens.
        Preserva todas as instruções críticas.
        """
        if self._count_tokens(prompt) <= self.max_tokens:
            return prompt  # já dentro do limite

        # Passo 1: Remove linhas duplicadas consecutivas
        prompt = self._remove_duplicates(prompt)

        if self._count_tokens(prompt) <= self.max_tokens:
            return prompt

        # Passo 2: Colapsa exemplos verbose
        prompt = self._collapse_verbose(prompt)

        if self._count_tokens(prompt) <= self.max_tokens:
            return prompt

        # Passo 3: Trunca seções de baixa prioridade
        prompt = self._truncate_low_priority(prompt)

        return prompt

    def _count_tokens(self, text: str) -> int:
        """Estimativa: 4 chars ≈ 1 token (heurística conservadora)."""
        return len(text) // 4

    def _is_critical(self, line: str) -> bool:
        """Verifica se a linha contém marcadores críticos."""
        return any(marker in line for marker in self.CRITICAL_MARKERS)

    def _remove_duplicates(self, prompt: str) -> str:
        """Remove linhas duplicadas consecutivas."""
        lines = prompt.split("\n")
        result = []
        prev = None
        for line in lines:
            stripped = line.strip()
            if stripped and stripped == prev:
                continue
            result.append(line)
            prev = stripped
        return "\n".join(result)

    def _collapse_verbose(self, prompt: str) -> str:
        """
        Colapsa seções verbose preservando críticas.
        Estratégia: reduz sequências de exemplos para 1 exemplo.
        """
        lines = prompt.split("\n")
        result = []
        example_count = 0
        in_example = False

        for line in lines:
            # Detecta início de exemplo
            is_example_start = (
                line.strip().startswith("Ex:") or
                line.strip().startswith("Exemplo:") or
                line.strip().startswith("  →") or
                (line.strip().startswith("-") and len(line.strip()) > 60)
            )

            if is_example_start and not self._is_critical(line):
                example_count += 1
                if example_count > 2:
                    # Colapsa exemplos além do 2º
                    if example_count == 3:
                        result.append("  [... exemplos adicionais omitidos ...]")
                    continue
            else:
                if not is_example_start:
                    example_count = 0

            result.append(line)

        return "\n".join(result)

    def _truncate_low_priority(self, prompt: str) -> str:
        """
        Trunca o prompt preservando:
        - Todas as linhas críticas
        - O início (primeiras 30 linhas)
        - O final (últimas 10 linhas)
        - Linhas críticas no meio
        """
        lines = prompt.split("\n")
        total = len(lines)
        target_lines = self.max_tokens * 4 // 60  # estimativa de chars por linha

        if total <= target_lines:
            return prompt

        # Sempre inclui: início + fim + linhas críticas
        keep = set()

        # Início (primeiras 30 linhas)
        for i in range(min(30, total)):
            keep.add(i)

        # Fim (últimas 10 linhas)
        for i in range(max(0, total - 10), total):
            keep.add(i)

        # Linhas críticas no meio
        for i, line in enumerate(lines):
            if self._is_critical(line):
                keep.add(i)
                # Adiciona contexto: linha anterior e posterior
                if i > 0:
                    keep.add(i - 1)
                if i < total - 1:
                    keep.add(i + 1)

        # Reconstrói com marcador de omissão
        result = []
        prev_included = True
        for i, line in enumerate(lines):
            if i in keep:
                if not prev_included and result:
                    result.append("  [...]")
                result.append(line)
                prev_included = True
            else:
                prev_included = False

        return "\n".join(result)


# ══════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM llm_client.py
# ══════════════════════════════════════════════════════════════════
#
# Em llm_client.py, substitua _parse_json_response por:
#
#   from kosmos_parser import RobustParser, PromptCompressor
#   _parser = RobustParser()
#   _compressor = PromptCompressor(max_tokens=3000)
#
#   def _parse_json_response(self, content: str) -> Dict[str, Any]:
#       return _parser.parse(content)
#
#   # Na montagem do system prompt:
#   compressed_protocol = _compressor.compress(_active_prompt)
#   content = self.chat(user_message=user_msg, system_prompt=compressed_protocol)


if __name__ == "__main__":
    # Demo rápido
    parser = RobustParser()

    cases = [
        ('Normal', '{"code": "print(1)", "strategy": "test"}'),
        ('Markdown', '```json\n{"code": "print(2)"}\n```'),
        ('Truncado', '{"code": "print(3)', ),
        ('HTML', '{"tool": "write_file", "content": "<!DOCTYPE html><html></html>"}'),
    ]

    print("RobustParser — Demo:")
    for name, case in cases:
        result = parser.parse(case)
        valid = "✓" if (result.get("code") or result.get("content")) else "✗"
        print(f"  {valid} {name}: {list(result.keys())}")

    compressor = PromptCompressor(max_tokens=500)
    big_prompt = "PROIBIDO usar isso\n" + "linha repetida\n" * 200 + "OBRIGATÓRIO fazer aquilo\n"
    compressed = compressor.compress(big_prompt)
    print(f"\nPromptCompressor: {len(big_prompt)//4} → {len(compressed)//4} tokens")
    print(f"  PROIBIDO preservado: {'PROIBIDO' in compressed}")
    print(f"  OBRIGATÓRIO preservado: {'OBRIGATÓRIO' in compressed}")
