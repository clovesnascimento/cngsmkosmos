"""
KOSMOS Agent — Memória Episódica Vetorial [SECURITY PATCH v2.1]
===============================================================
Correções aplicadas (Red Team Audit):
  [ATK-08] Sanitização de segredos (API keys, senhas) antes de armazenar
  [ATK-03] Score de confiança para mitigar RAG Poisoning (não armazena episódios
           suspeitos com rotas inseguras marcadas como sucesso)
"""

import re
import time
import logging
import hashlib
from typing import Dict, Any, List, Optional

import numpy as np

logger = logging.getLogger("kosmos.memory")

EMBED_DIM = 128

# ─── [ATK-08] Padrões de segredos a sanitizar ───
SECRET_PATTERNS = [
    # API Keys genéricas
    (re.compile(r'\b(sk-[a-zA-Z0-9]{20,})\b'), '[REDACTED_API_KEY]'),
    (re.compile(r'\b(key-[a-zA-Z0-9]{16,})\b'), '[REDACTED_KEY]'),
    # AWS
    (re.compile(r'\b(AKIA[0-9A-Z]{16})\b'), '[REDACTED_AWS_KEY]'),
    (re.compile(r'aws_secret_access_key\s*=\s*\S+', re.IGNORECASE), 'aws_secret_access_key=[REDACTED]'),
    # DeepSeek / OpenAI style
    (re.compile(r'\b(sk-[a-zA-Z0-9\-]{30,})\b'), '[REDACTED_SK_KEY]'),
    # Passwords em strings comuns
    (re.compile(r'(password|passwd|pwd|secret)\s*[:=]\s*\S+', re.IGNORECASE), r'\1=[REDACTED]'),
    # Tokens Bearer
    (re.compile(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE), 'Bearer [REDACTED_TOKEN]'),
    # GitHub tokens
    (re.compile(r'\b(ghp_[a-zA-Z0-9]{36})\b'), '[REDACTED_GH_TOKEN]'),
    # Cartões de crédito (formato básico)
    (re.compile(r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b'), '[REDACTED_CARD]'),
]

# [ATK-03] Rotas que NÃO devem ser armazenadas como "sucesso" (sanity check)
UNSAFE_ROUTE_MARKERS = ["python_unsafe", "_fallback_execute"]


def _sanitize_text(text: str) -> str:
    """
    [ATK-08] Remove segredos conhecidos de um texto antes de armazenar na memória.
    """
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _text_to_hash_embedding(text: str, dim: int = EMBED_DIM) -> np.ndarray:
    """Gera embedding determinístico a partir de hash do texto."""
    h = hashlib.sha512(text.encode("utf-8")).digest()
    repeated = h * ((dim * 4 // len(h)) + 1)
    arr = np.frombuffer(repeated[:dim * 4], dtype=np.float32)[:dim]
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr


class Episode:
    """Um episódio do loop cognitivo — com texto sanitizado."""

    def __init__(
        self,
        task: str,
        plan: Dict[str, Any],
        result: Dict[str, Any],
        critique: Dict[str, Any],
        iteration: int = 0,
    ):
        # [ATK-08] Sanitiza task e output antes de armazenar
        self.task     = _sanitize_text(task)
        self.plan     = plan
        self.result   = result
        self.critique = critique
        self.iteration = iteration
        self.timestamp = time.time()

    def to_text(self) -> str:
        """Serializa episódio para texto (embedding)."""
        # [ATK-08] Sanitiza novamente na geração do texto para o embedding
        thought_raw = self.plan.get('thought', '')
        thought = _sanitize_text(thought_raw)
        parts = [
            f"task: {self.task}",
            f"thought: {thought}",
            f"tool: {self.plan.get('tool', '')}",
            f"success: {self.critique.get('success', False)}",
        ]
        if self.critique.get("feedback"):
            parts.append(f"feedback: {_sanitize_text(self.critique['feedback'])}")
        return " | ".join(parts)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "plan": self.plan,
            "result": self.result,
            "critique": self.critique,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
        }


class EpisodicMemory:
    """
    Memória episódica com busca por similaridade vetorial (FAISS).
    [ATK-08] Sanitiza segredos antes de armazenar.
    [ATK-03] Recusa armazenar episódios suspeitos de RAG Poisoning.
    """

    def __init__(self, dim: int = EMBED_DIM):
        self.dim = dim
        self.episodes: List[Episode] = []
        self._index = None
        self._blocked_count = 0
        self._init_index()

    def _init_index(self):
        try:
            import faiss
            self._index = faiss.IndexFlatL2(self.dim)
            logger.info(f"FAISS IndexFlatL2({self.dim}) inicializado")
        except ImportError:
            logger.warning("faiss-cpu não instalado. Usando busca linear como fallback.")
            self._index = None

    def embed(self, text: str) -> np.ndarray:
        return _text_to_hash_embedding(text, self.dim)

    def _is_suspicious_episode(
        self,
        plan: Dict[str, Any],
        critique: Dict[str, Any],
    ) -> Optional[str]:
        """
        [ATK-03] Detecta episódios suspeitos que podem envenenar a memória:
        - Sucesso reportado ao usar rotas inseguras
        - Plano com strings de prompt injection
        Retorna motivo se suspeito, None se ok.
        """
        tool = plan.get("tool", "")
        code = plan.get("code", "")
        thought = plan.get("thought", "")
        reported_success = critique.get("success", False)

        # Rota insegura reportada como sucesso
        for marker in UNSAFE_ROUTE_MARKERS:
            if marker in tool and reported_success:
                return f"Rota insegura '{marker}' marcada como sucesso"

        # Prompt injection no thought ou code
        injection_markers = [
            "atenção sistema",
            "obrigatoriamente a tool",
            "sandbox falhou",
            "use python_unsafe",
        ]
        combined = (thought + " " + code).lower()
        for marker in injection_markers:
            if marker in combined:
                return f"Possível prompt injection detectado: '{marker}'"

        return None

    def store(
        self,
        task: str,
        plan: Dict[str, Any],
        result: Dict[str, Any],
        critique: Dict[str, Any],
        iteration: int = 0,
    ):
        """
        Armazena um episódio na memória.
        [ATK-08] Sanitiza segredos. [ATK-03] Bloqueia episódios suspeitos.
        """
        # [ATK-03] Bloqueia episódios suspeitos de RAG Poisoning
        suspicion = self._is_suspicious_episode(plan, critique)
        if suspicion:
            self._blocked_count += 1
            logger.warning(
                f"[SECURITY][ATK-03] Episódio bloqueado da memória: {suspicion} "
                f"(total bloqueados: {self._blocked_count})"
            )
            return

        episode = Episode(task, plan, result, critique, iteration)
        self.episodes.append(episode)

        vector = self.embed(episode.to_text())
        if self._index is not None:
            self._index.add(vector.reshape(1, -1))

        logger.debug(
            f"Episódio armazenado: task='{episode.task[:50]}', "
            f"success={critique.get('success')}, "
            f"total={len(self.episodes)}"
        )

    def search(self, query: str, k: int = 5) -> List[Episode]:
        if not self.episodes:
            return []
        k = min(k, len(self.episodes))
        if self._index is not None:
            vector = self.embed(query).reshape(1, -1)
            distances, indices = self._index.search(vector, k)
            return [self.episodes[i] for i in indices[0] if i < len(self.episodes)]
        return self._linear_search(query, k)

    def _linear_search(self, query: str, k: int) -> List[Episode]:
        query_vec = self.embed(query)
        scored = []
        for ep in self.episodes:
            ep_vec = self.embed(ep.to_text())
            dot = np.dot(query_vec, ep_vec)
            norm_q = np.linalg.norm(query_vec)
            norm_e = np.linalg.norm(ep_vec)
            similarity = dot / (norm_q * norm_e + 1e-8)
            scored.append((similarity, ep))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:k]]

    def get_recent(self, n: int = 5) -> List[Episode]:
        return self.episodes[-n:]

    def get_failures(self) -> List[Episode]:
        return [ep for ep in self.episodes if not ep.critique.get("success", False)]

    def get_successes(self) -> List[Episode]:
        return [ep for ep in self.episodes if ep.critique.get("success", False)]

    def summary(self) -> Dict[str, Any]:
        total = len(self.episodes)
        successes = len(self.get_successes())
        return {
            "total_episodes": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total > 0 else 0,
            "blocked_suspicious": self._blocked_count,
        }

    def clear(self):
        self.episodes.clear()
        self._init_index()
        logger.info("Memória limpa")
