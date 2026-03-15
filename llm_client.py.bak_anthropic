"""
KOSMOS Agent — DeepSeek LLM Client
====================================
Cliente para a API DeepSeek (OpenAI-compatible).
Usado pelo ProposerAgent e ReviewerAgent para gerar
pensamentos e código real via LLM.
"""

import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("kosmos.llm")

# ─── Config ───

DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_CODER_MODEL = "deepseek-coder"


@dataclass
class LLMConfig:
    """Configuração do cliente LLM."""
    api_key: str = ""
    api_base: str = os.environ.get("DEEPSEEK_API_BASE", DEEPSEEK_API_BASE)
    model: str = os.environ.get("DEEPSEEK_MODEL", DEEPSEEK_MODEL)
    coder_model: str = os.environ.get("DEEPSEEK_CODER_MODEL", DEEPSEEK_CODER_MODEL)
    temperature: float = 0.7
    max_tokens: int = 4096  # Suporta gerações massivas
    timeout: int = 600      # 10 MINUTOS (Claude-Code Style) para evitar perdas em Landing Pages
    retry_count: int = 3
    retry_delay: float = 5.0


# ─── Sistema de prompts ───

SYSTEM_PROMPT_PROPOSER = """Você é um agente de planejamento cognitivo (KOSMOS-4).
Sua tarefa é analisar problemas e gerar código Python para resolvê-los.

REGRAS:
1. Gere APENAS código Python válido e executável.
2. REGRA ABSOLUTA para HTML/CSS/JS: encode em base64 e decode no script.
   UNICO metodo permitido para landing pages:
     import base64, codecs
     html = codecs.encode(b"<html>...</html>", "base64").decode()
     open("index.html","wb").write(base64.b64decode(html))
   PROIBIDO: f.write() com strings multiline, aspas simples/duplas com HTML.
3. O diretorio atual JA EH o workspace. Use open("index.html","w") diretamente. NUNCA workspace/index.html.
4. Use print() com mensagem de 50+ chars mostrando o arquivo criado e tamanho.
5. Trate erros com try/except.
6. Seja conciso e eficiente.

Para tarefas de criacao de arquivos HTML/CSS/JS, use tool=write_file:
OPCAO A - write_file (PREFERIDO para HTML/landing pages):
{
    "thought": "raciocinio",
    "tool": "write_file",
    "path": "index.html",
    "content": "<!DOCTYPE html><html>...</html>",
    "strategy": "nome da estrategia"
}
OPCAO B - python (para logica, calculos, scripts):
{
    "thought": "raciocinio",
    "code": "codigo python completo",
    "strategy": "nome da estrategia"
}
"""

SYSTEM_PROMPT_REVIEWER = """Você é um revisor de código (KOSMOS-4 Reviewer).
Avalie a proposta de código recebida com base em:

1. Correção (o código resolve o problema?)
2. Eficiência (é performático?)
3. Robustez (trata erros?)
4. Clareza (é legível?)
5. Completude (produz output?)

Responda em formato JSON:
{
    "score": 0.0-1.0,
    "feedback": "feedback detalhado",
    "approved": true/false,
    "improvements": ["sugestão 1", "sugestão 2"]
}"""

SYSTEM_PROMPT_REFLEXION = """Voce e um critico cognitivo (KOSMOS-4 Reflexion).
Analise o resultado da execucao de codigo e determine:

1. Se foi bem-sucedido
2. O que deu errado (se aplicavel)
3. Como corrigir/melhorar

Responda em formato JSON:
{
    "success": true/false,
    "analysis": "analise detalhada",
    "replan": "instrucao de replanejamento se falhou",
    "confidence": 0.0-1.0
}"""

SYSTEM_PROMPT_INTENT = """Analise a TAREFA do usuario e classifique-a em uma categoria:
1. "CHAT": Conversa informal, saudações (oi, olá), perguntas sobre quem você é, ou dúvidas genéricas que NÃO exigem execução de código ou manipulação de arquivos.
2. "TECHNICAL": Problemas matemáticos, criação de scripts, manipulação de arquivos no workspace, análise de dados ou qualquer tarefa que EXIJA execução de código Python.

Responda APENAS com a palavra "CHAT" ou "TECHNICAL"."""

SYSTEM_PROMPT_CHAT = """Você é o CNGSM CODE, um agente cognitivo amigável e ultra-inteligente. 
Responda de forma concisa e útil. Se o usuário quiser fazer algo técnico, diga que está pronto para executar."""


class DeepSeekClient:
    """
    Cliente para a API DeepSeek.
    Usa requests para fazer chamadas HTTP diretas (OpenAI-compatible API).

    Uso:
        client = DeepSeekClient(api_key="sk-...")
        response = client.chat("Olá, como resolver fibonacci?")
        code = client.generate_code("Calcular fibonacci de 10")
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()

        # API key via config ou env var
        self.api_key = (
            self.config.api_key
            or os.environ.get("DEEPSEEK_API_KEY", "")
        )

        if not self.api_key:
            logger.warning(
                "DeepSeek API key não configurada. "
                "Set DEEPSEEK_API_KEY ou passe via LLMConfig."
            )

        self._request_count = 0
        self._total_tokens = 0

        logger.info(
            f"DeepSeekClient inicializado "
            f"(model={self.config.model}, "
            f"base={self.config.api_base})"
        )

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extrai JSON de uma string, tratando blocos de código e truncamento."""
        import json
        import re
        
        # 1. Tenta encontrar bloco de código markdown ```json ... ``` ou ``` ... ```
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        
        text = text.strip()
        if not text: return None
        
        # 2. Tenta parse direto do texto limpo
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
            
        # 3. Se falhou, busca o primeiro { e tenta extrair o objeto
        start = text.find("{")
        if start == -1: return None
        json_part = text[start:].strip()
        
        # 4. Tenta encontrar o fechamento correto balanceando chaves
        brackets_stack = []
        last_idx = 0
        in_string = False
        escape = False
        
        for i, char in enumerate(json_part):
            if char == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if char == '{': brackets_stack.append('}')
                elif char == '[': brackets_stack.append(']')
                elif char in ['}', ']']:
                    if brackets_stack and char == brackets_stack[-1]:
                        brackets_stack.pop()
                        if not brackets_stack:
                            last_idx = i + 1
                            break
            escape = (char == '\\' and not escape)
            
        if last_idx > 0:
            candidate = json_part[:last_idx]
            try:
                return json.loads(candidate)
            except:
                pass
                
        # 5. Fallback Final: Extrator Manual por Marcador (para códigos gigantes truncados)
        # Se falhou tudo, tentamos pegar campos via regex robusta
        result = {}
        # Busca recursiva para os campos principais
        for key in ["thought", "code", "strategy"]:
            # Procura a chave e captura tudo até a próxima chave conhecida ou o fim
            pattern = rf'"{key}"\s*:\s*"'
            m = re.search(pattern, json_part)
            if m:
                v_start = m.end()
                # Tenta achar o separador de campo JSON: ", "key" :
                # Ou o fechamento do objeto: " }
                next_key = re.search(r'",\s*"(thought|code|strategy|result)"\s*:', json_part[v_start:])
                if next_key:
                    v_end = v_start + next_key.start()
                else:
                    v_end = json_part.rfind('"')
                
                if v_end > v_start:
                    val = json_part[v_start:v_end]
                    # Desfaz aspas e quebras de linha escapadas
                    val = val.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
                    result[key] = val
                    
        return result if "code" in result else None

    def _make_request(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Faz request à API DeepSeek (OpenAI-compatible).
        Retorna o response dict parsed.
        """
        import requests

        # Constrói URL: se a base já tem /v1, não acrescenta
        base = self.config.api_base.rstrip("/")
        if "/v1" in base:
            url = f"{base}/chat/completions"
        else:
            url = f"{base}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model or self.config.model,
            "messages": messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": False,
        }

        for attempt in range(self.config.retry_count):
            try:
                logger.info(f"Chamando DeepSeek API ({len(payload['messages'])} mensagens)...")
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout,
                )
                logger.info(f"Resposta recebida da DeepSeek API (status={response.status_code})")

                self._request_count += 1

                if response.status_code == 200:
                    data = response.json()
                    # Track token usage
                    usage = data.get("usage", {})
                    self._total_tokens += usage.get("total_tokens", 0)

                    logger.debug(
                        f"API call #{self._request_count}: "
                        f"tokens={usage.get('total_tokens', '?')}"
                    )
                    return data

                elif response.status_code == 429:
                    # Rate limit — backoff exponencial
                    wait = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retry em {wait:.1f}s...")
                    time.sleep(wait)
                    continue

                else:
                    error_body = response.text[:500]
                    logger.error(
                        f"API error {response.status_code}: {error_body}"
                    )
                    return {
                        "error": True,
                        "status_code": response.status_code,
                        "message": error_body,
                    }

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout (attempt {attempt + 1})")
                if attempt < self.config.retry_count - 1:
                    time.sleep(self.config.retry_delay)
                continue

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error: {e}")
                return {
                    "error": True,
                    "message": f"Connection error: {e}",
                }

            except Exception as e:
                logger.error(f"Request exception: {e}")
                return {
                    "error": True,
                    "message": str(e),
                }

        return {
            "error": True,
            "message": f"Max retries ({self.config.retry_count}) exceeded",
        }

    def _extract_content(self, response: Dict) -> str:
        """Extrai o content text do response."""
        if response.get("error"):
            return ""

        try:
            choices = response.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
        except (KeyError, IndexError):
            pass

        return ""

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """
        Parseia resposta JSON do LLM.
        Trata casos onde o LLM envolve em ```json ... ```.
        """
        content = content.strip()

        parsed_json = self._extract_json(content)
        if parsed_json is not None:
            return parsed_json

        logger.warning(f"Falha ao parsear JSON: {content[:200]}")
        return {"raw": content}

    # ─── API pública ───

    def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Chat simples com o LLM, suportando historico e parametros.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if history:
            messages.extend(history)
            
        messages.append({"role": "user", "content": user_message})

        response = self._make_request(
            messages, 
            model=model, 
            temperature=temperature, 
            max_tokens=max_tokens
        )
        return self._extract_content(response)

    def detect_intent(self, task: str) -> str:
        """Determina se a tarefa e CHAT ou TECHNICAL."""
        # Heuristica rapida para evitar chamada de rede se for muito obvio
        task_lower = task.lower().strip().strip("?!.")
        greetings = ["oi", "ola", "hello", "bom dia", "boa tarde", "boa noite", "quem e voce", "quem e vc"]
        if task_lower in greetings:
            return "CHAT"
            
        # Chamada ao LLM para casos ambiguos
        intent = self.chat(
            user_message=f"Tarefa: {task}",
            system_prompt=SYSTEM_PROMPT_INTENT,
            temperature=0.0,
            max_tokens=10
        )
        return "CHAT" if "CHAT" in intent.upper() else "TECHNICAL"

    def generate_proposal(self, task: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Gera uma proposta de código para resolver a tarefa.
        Usado pelo ProposerAgent.

        Returns:
            {"thought": str, "code": str, "strategy": str}
        """
        user_msg = f"TAREFA: {task}"
        if context:
            user_msg += f"\n\nCONTEXTO ADICIONAL:\n{context}"

        logger.info(f"LLM: Gerando proposta para '{task[:50]}...'")
        # [KOSMOS-v2.3] SkillRouter integrado
        _skill_protocol = ""
        try:
            from skill_router import SkillRouter
            from skill_forge import SkillForge
            if not hasattr(self, "_skill_router"):
                self._skill_router = SkillRouter()
                self._skill_forge  = SkillForge("skills_registry.json")
            _skill_protocol = self._skill_router.route(task)
            if not _skill_protocol:
                forged = self._skill_forge.forge(task)
                if forged:
                    _skill_protocol = forged.protocol
            if _skill_protocol:
                import logging as _lg
                _lg.getLogger("kosmos.llm").info(
                    f"SkillRouter: protocolo injetado para '{task[:40]}...'"
                )
        except Exception as _e:
            import logging as _lg
            _lg.getLogger("kosmos.llm").warning(
                f"SkillRouter: falhou ({_e}), usando base prompt"
            )
        _active_prompt = SYSTEM_PROMPT_PROPOSER + _skill_protocol
        content = self.chat(
            user_message=user_msg,
            system_prompt=_active_prompt,
        )
        logger.info("LLM: Proposta gerada com sucesso")

        if not content:
            msg = f"[AUTO-DEV] Erro: LLM offline para tarefa: {task}"
            return {
                "thought": "LLM não retornou resposta (Timeout ou Erro de Rede)",
                "code": f"print({repr(msg)})",
                "strategy": "fallback",
            }

        parsed = self._parse_json_response(content)
        
        if not parsed or not parsed.get("code"):
            msg = f"[AUTO-DEV] Erro de Parse na resposta do LLM para: {task}"
            return {
                "thought": f"Falha ao extrair JSON da resposta: {content[:100]}...",
                "code": f"print({repr(msg)})",
                "strategy": "fix_json",
            }

        # Garante campos obrigatórios
        return {
            "thought": parsed.get("thought", "Sem pensamento"),
            "code": parsed.get("code", f"print('Tarefa: {task}')"),
            "strategy": parsed.get("strategy", "llm_generated"),
        }

    def review_proposal(self, task: str, proposal: Dict) -> Dict[str, Any]:
        """
        Revisa uma proposta de código.
        Usado pelo ReviewerAgent.

        Returns:
            {"score": float, "feedback": str, "approved": bool}
        """
        user_msg = (
            f"TAREFA: {task}\n\n"
            f"PROPOSTA:\n"
            f"Thought: {proposal.get('thought', '')}\n"
            f"Strategy: {proposal.get('strategy', '')}\n"
            f"Code:\n```python\n{proposal.get('code', '')}\n```"
        )

        content = self.chat(
            user_message=user_msg,
            system_prompt=SYSTEM_PROMPT_REVIEWER,
        )

        if not content:
            return {
                "score": 0.5,
                "feedback": "LLM reviewer offline",
                "approved": True,
                "improvements": [],
            }

        parsed = self._parse_json_response(content)

        return {
            "score": float(parsed.get("score", 0.5)),
            "feedback": parsed.get("feedback", "Sem feedback"),
            "approved": parsed.get("approved", True),
            "improvements": parsed.get("improvements", []),
        }

    def reflexion_evaluate(
        self,
        task: str,
        plan: Dict,
        result: Dict,
    ) -> Dict[str, Any]:
        """
        Avaliação reflexiva do resultado.
        Usado pelo Reflexion critic.

        Returns:
            {"success": bool, "analysis": str, "replan": str, "confidence": float}
        """
        user_msg = (
            f"TAREFA: {task}\n\n"
            f"PLANO EXECUTADO:\n"
            f"Thought: {plan.get('thought', '')}\n"
            f"Code:\n```python\n{plan.get('code', '')}\n```\n\n"
            f"RESULTADO:\n"
            f"Output: {result.get('output', 'Nenhum')}\n"
            f"Error: {result.get('error', 'Nenhum')}\n"
            f"Exit Code: {result.get('exit_code', -1)}"
        )

        content = self.chat(
            user_message=user_msg,
            system_prompt=SYSTEM_PROMPT_REFLEXION,
        )

        if not content:
            return {
                "success": result.get("exit_code", -1) == 0,
                "analysis": "LLM reflexion offline",
                "replan": None,
                "confidence": 0.3,
            }

        parsed = self._parse_json_response(content)

        return {
            "success": parsed.get("success", False),
            "analysis": parsed.get("analysis", "Sem análise"),
            "replan": parsed.get("replan"),
            "confidence": float(parsed.get("confidence", 0.5)),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso da API."""
        return {
            "total_requests": self._request_count,
            "total_tokens": self._total_tokens,
            "model": self.config.model,
            "api_base": self.config.api_base,
        }


# ─── Singleton para acesso global ───

_global_client: Optional[DeepSeekClient] = None


def get_llm_client(config: Optional[LLMConfig] = None) -> DeepSeekClient:
    """Obtém ou cria o cliente LLM global."""
    global _global_client
    if _global_client is None:
        _global_client = DeepSeekClient(config)
    return _global_client


def set_api_key(key: str):
    """Configura a API key globalmente."""
    global _global_client
    config = LLMConfig(api_key=key)
    _global_client = DeepSeekClient(config)
