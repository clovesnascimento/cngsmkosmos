"""
KOSMOS Agent — Memória Episódica Vetorial (FAISS)
==================================================
Armazena episódios (task, plan, result, critique) com embeddings vetoriais.
Busca por similaridade para informar o loop cognitivo.
"""

import time
import logging
import hashlib
from typing import Dict, Any, List, Optional

import numpy as np

logger = logging.getLogger("kosmos.memory")

# Dimensão do embedding
EMBED_DIM = 128


def _text_to_hash_embedding(text: str, dim: int = EMBED_DIM) -> np.ndarray:
    """
    Gera embedding determinístico a partir de hash do texto.
    Placeholder para embedding real via LLM (ex: sentence-transformers).

    Para produção, substituir por:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        return model.encode(text)
    """
    h = hashlib.sha512(text.encode("utf-8")).digest()
    # Expande hash para preencher a dimensão
    repeated = h * ((dim * 4 // len(h)) + 1)
    arr = np.frombuffer(repeated[:dim * 4], dtype=np.float32)[:dim]
    # Normaliza para L2
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr


class Episode:
    """Um episódio do loop cognitivo."""

    def __init__(
        self,
        task: str,
        plan: Dict[str, Any],
        result: Dict[str, Any],
        critique: Dict[str, Any],
        iteration: int = 0,
    ):
        self.task = task
        self.plan = plan
        self.result = result
        self.critique = critique
        self.iteration = iteration
        self.timestamp = time.time()

    def to_text(self) -> str:
        """Serializa episódio para texto (usado na geração de embedding)."""
        parts = [
            f"task: {self.task}",
            f"thought: {self.plan.get('thought', '')}",
            f"tool: {self.plan.get('tool', '')}",
            f"success: {self.critique.get('success', False)}",
        ]
        if self.critique.get("feedback"):
            parts.append(f"feedback: {self.critique['feedback']}")
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

    Armazena episódios do loop cognitivo e permite busca para
    informar decisões futuras (evitar repetir erros, reutilizar soluções).

    Uso:
        memory = EpisodicMemory()
        memory.store(task, plan, result, critique)
        similar = memory.search("calcular fibonacci")
    """

    def __init__(self, dim: int = EMBED_DIM):
        self.dim = dim
        self.episodes: List[Episode] = []
        self._index = None
        self._init_index()

    def _init_index(self):
        """Inicializa índice FAISS."""
        try:
            import faiss
            self._index = faiss.IndexFlatL2(self.dim)
            logger.info(f"FAISS IndexFlatL2({self.dim}) inicializado")
        except ImportError:
            logger.warning(
                "faiss-cpu não instalado. Usando busca linear como fallback."
            )
            self._index = None

    def embed(self, text: str) -> np.ndarray:
        """Gera embedding para texto."""
        return _text_to_hash_embedding(text, self.dim)

    def store(
        self,
        task: str,
        plan: Dict[str, Any],
        result: Dict[str, Any],
        critique: Dict[str, Any],
        iteration: int = 0,
    ):
        """Armazena um episódio na memória."""
        episode = Episode(task, plan, result, critique, iteration)
        self.episodes.append(episode)

        vector = self.embed(episode.to_text())

        if self._index is not None:
            self._index.add(vector.reshape(1, -1))

        logger.debug(
            f"Episódio armazenado: task='{task}', "
            f"success={critique.get('success')}, "
            f"total={len(self.episodes)}"
        )

    def search(self, query: str, k: int = 5) -> List[Episode]:
        """
        Busca episódios similares à query.

        Args:
            query: texto da busca
            k: número máximo de resultados

        Returns:
            Lista de episódios ordenados por similaridade
        """
        if not self.episodes:
            return []

        k = min(k, len(self.episodes))

        if self._index is not None:
            vector = self.embed(query).reshape(1, -1)
            distances, indices = self._index.search(vector, k)
            return [self.episodes[i] for i in indices[0] if i < len(self.episodes)]
        else:
            # Fallback: busca linear
            return self._linear_search(query, k)

    def _linear_search(self, query: str, k: int) -> List[Episode]:
        """Busca por similaridade via cosine similarity (fallback sem FAISS)."""
        query_vec = self.embed(query)

        scored = []
        for ep in self.episodes:
            ep_vec = self.embed(ep.to_text())
            # Cosine similarity
            dot = np.dot(query_vec, ep_vec)
            norm_q = np.linalg.norm(query_vec)
            norm_e = np.linalg.norm(ep_vec)
            similarity = dot / (norm_q * norm_e + 1e-8)
            scored.append((similarity, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:k]]

    def get_recent(self, n: int = 5) -> List[Episode]:
        """Retorna os N episódios mais recentes."""
        return self.episodes[-n:]

    def get_failures(self) -> List[Episode]:
        """Retorna todos os episódios com falha."""
        return [ep for ep in self.episodes if not ep.critique.get("success", False)]

    def get_successes(self) -> List[Episode]:
        """Retorna todos os episódios com sucesso."""
        return [ep for ep in self.episodes if ep.critique.get("success", False)]

    def summary(self) -> Dict[str, Any]:
        """Resumo estatístico da memória."""
        total = len(self.episodes)
        successes = len(self.get_successes())
        failures = len(self.get_failures())

        return {
            "total_episodes": total,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / total if total > 0 else 0,
        }

    def clear(self):
        """Limpa toda a memória."""
        self.episodes.clear()
        self._init_index()
        logger.info("Memória limpa")
