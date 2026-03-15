"""
kosmos_memory.py — KOSMOS Stage 3 Solution
===========================================
F6 — Memória episódica persistente com SQLite
    - Substitui FAISS volátil por SQLite (zero dependências extras)
    - Episódios persistem entre sessões e processos
    - Busca por similaridade via TF-IDF simples (sem embeddings externos)
    - Compatível com Windows e Linux

F7 — Injeção proativa de lições aprendidas
    - Busca episódios similares à tarefa atual
    - Filtra episódios com lições marcadas como críticas
    - Injeta contexto compacto no system prompt
    - Evita injetar lições irrelevantes (threshold de similaridade)

Sem dependências externas além da stdlib Python.
ChromaDB pode ser usado como backend alternativo se disponível.
"""

import os
import re
import json
import math
import sqlite3
import logging
import hashlib
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("kosmos.memory")

# ── Config ────────────────────────────────────────────────────────
DEFAULT_DB_PATH    = "kosmos_memory.db"
DEFAULT_TOP_K      = 5
SIMILARITY_THRESHOLD = 0.15   # mínimo de relevância para injetar lição
MAX_LESSON_LENGTH  = 200      # trunca lições longas no prompt


# ══════════════════════════════════════════════════════════════════
# KOSMOS MEMORY
# ══════════════════════════════════════════════════════════════════

class KosmosMemory:
    """
    Memória episódica persistente para o KOSMOS Agent.

    Armazena episódios (tarefa + resultado + lição) em SQLite.
    Busca episódios relevantes via TF-IDF para injeção proativa no prompt.

    Compatível com o memory.py existente via KosmosMemoryAdapter.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._conn   = None
        self._init_db()
        logger.info(f"KosmosMemory inicializado: {self.db_path}")

    # ── Inicialização ─────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """Conexão lazy — cria se não existe."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        """Cria as tabelas se não existirem."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task        TEXT NOT NULL,
                task_hash   TEXT NOT NULL,
                success     INTEGER NOT NULL,
                error       TEXT,
                strategy    TEXT,
                lesson      TEXT,
                tokens      TEXT,
                created_at  TEXT NOT NULL,
                session_id  TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_hash ON episodes(task_hash)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_success ON episodes(success)
        """)
        conn.commit()

    # ── Operações CRUD ────────────────────────────────────────────

    def store_episode(
        self,
        task: str,
        success: bool,
        error: Optional[str] = None,
        strategy: Optional[str] = None,
        lesson: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Armazena um episódio e retorna o ID."""
        tokens = json.dumps(self._tokenize(task))
        task_hash = hashlib.md5(task.encode()).hexdigest()[:16]

        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO episodes
                (task, task_hash, success, error, strategy, lesson, tokens, created_at, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task, task_hash, int(success), error, strategy,
                lesson, tokens, datetime.now().isoformat(), session_id,
            )
        )
        conn.commit()
        episode_id = cursor.lastrowid
        logger.debug(f"Episódio #{episode_id} armazenado: task='{task[:50]}' success={success}")
        return episode_id

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        only_failures: bool = False,
        only_lessons: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Busca episódios similares à query via TF-IDF.
        Retorna lista ordenada por relevância.
        """
        conn = self._get_conn()

        # Filtra por critérios
        conditions = []
        if only_failures:
            conditions.append("success = 0")
        if only_lessons:
            conditions.append("lesson IS NOT NULL AND lesson != ''")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(
            f"SELECT * FROM episodes {where} ORDER BY id DESC LIMIT 200"
        ).fetchall()

        if not rows:
            return []

        # Calcula similaridade TF-IDF
        query_tokens = set(self._tokenize(query))
        scored = []

        for row in rows:
            try:
                doc_tokens = set(json.loads(row["tokens"]))
            except Exception:
                doc_tokens = set(self._tokenize(row["task"]))

            score = self._similarity(query_tokens, doc_tokens)
            if score > 0:
                scored.append((score, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]

    def get_prompt_injection(
        self,
        task: str,
        max_lessons: int = 3,
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> str:
        """
        Retorna texto formatado com lições aprendidas relevantes para a tarefa.
        Retorna string vazia se não há lições relevantes.
        """
        # Busca episódios com lições
        candidates = self.search(task, top_k=10, only_lessons=True)

        if not candidates:
            return ""

        # Filtra por threshold de similaridade
        query_tokens = set(self._tokenize(task))
        relevant = []

        for ep in candidates:
            try:
                doc_tokens = set(json.loads(ep.get("tokens", "[]")))
            except Exception:
                doc_tokens = set(self._tokenize(ep["task"]))

            score = self._similarity(query_tokens, doc_tokens)
            if score >= threshold:
                relevant.append((score, ep))

        if not relevant:
            return ""

        # Ordena por score e pega os top_k
        relevant.sort(key=lambda x: x[0], reverse=True)
        top = relevant[:max_lessons]

        # Formata injeção
        lines = ["\n[LIÇÕES APRENDIDAS — episódios similares desta sessão]"]

        for score, ep in top:
            lesson = ep.get("lesson", "")
            if not lesson:
                continue

            # Trunca lições longas
            if len(lesson) > MAX_LESSON_LENGTH:
                lesson = lesson[:MAX_LESSON_LENGTH] + "..."

            status = "✓" if ep.get("success") else "✗"
            strategy = ep.get("strategy", "?")
            lines.append(f"  {status} [{strategy}] {lesson}")

        if len(lines) <= 1:
            return ""

        lines.append("")
        return "\n".join(lines)

    def count(self) -> int:
        """Retorna o total de episódios armazenados."""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as n FROM episodes").fetchone()
        return row["n"] if row else 0

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna os episódios mais recentes."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM episodes ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Estatísticas da memória."""
        conn = self._get_conn()
        total   = self.count()
        success = conn.execute("SELECT COUNT(*) as n FROM episodes WHERE success=1").fetchone()["n"]
        lessons = conn.execute("SELECT COUNT(*) as n FROM episodes WHERE lesson IS NOT NULL AND lesson != ''").fetchone()["n"]
        return {
            "total":    total,
            "success":  success,
            "failures": total - success,
            "lessons":  lessons,
            "db_path":  str(self.db_path),
            "db_size":  f"{self.db_path.stat().st_size // 1024}KB" if self.db_path.exists() else "0KB",
        }

    # ── TF-IDF Similarity ─────────────────────────────────────────

    def _tokenize(self, text: str) -> List[str]:
        """Tokenização simples: lowercase, remove pontuação, split."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        # Remove stopwords básicas
        stopwords = {
            "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
            "em", "no", "na", "nos", "nas", "e", "é", "para", "por", "com",
            "que", "se", "the", "a", "an", "is", "are", "for", "to", "of",
        }
        return [t for t in tokens if t not in stopwords and len(t) > 2]

    def _similarity(self, tokens_a: set, tokens_b: set) -> float:
        """Jaccard similarity entre dois conjuntos de tokens."""
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = len(tokens_a & tokens_b)
        union        = len(tokens_a | tokens_b)
        return intersection / union if union > 0 else 0.0

    def __del__(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════
# ADAPTER — compatibilidade com memory.py existente
# ══════════════════════════════════════════════════════════════════

class KosmosMemoryAdapter:
    """
    Adapter que mantém a interface do memory.py existente
    mas persiste em SQLite via KosmosMemory.

    Integração no KosmosEngine (main.py ou agents.py):
        from kosmos_memory import KosmosMemoryAdapter
        self.memory = KosmosMemoryAdapter()

        # Armazenar (mesmo método do memory.py original):
        self.memory.store(task=task, success=success, ...)

        # Novo: obter injeção de lições para o prompt:
        injection = self.memory.get_prompt_injection(task)
        active_prompt = base_prompt + injection
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH, **kwargs):
        self._mem = KosmosMemory(db_path=db_path)
        # Compatibilidade com parâmetros do memory.py original
        self._faiss_index = None  # mantém referência por compatibilidade

    def store(
        self,
        task: str,
        success: bool,
        error: Optional[str] = None,
        strategy: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Interface compatível com memory.py original."""
        # Extrai lição do erro se disponível
        lesson = None
        if error and not success:
            lesson = self._extract_lesson(task, error, strategy)

        self._mem.store_episode(
            task=task,
            success=success,
            error=error,
            strategy=strategy,
            lesson=lesson,
        )

    def store_episode(self, *args, **kwargs):
        """Alias direto."""
        return self._mem.store_episode(*args, **kwargs)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        return self._mem.search(query, top_k=top_k)

    def get_prompt_injection(self, task: str, max_lessons: int = 3) -> str:
        return self._mem.get_prompt_injection(task, max_lessons=max_lessons)

    def count(self) -> int:
        return self._mem.count()

    def get_stats(self) -> Dict:
        return self._mem.get_stats()

    def _extract_lesson(
        self, task: str, error: str, strategy: Optional[str]
    ) -> Optional[str]:
        """
        Gera uma lição automaticamente a partir do erro.
        Lições são injetadas em tarefas futuras similares.
        """
        error_lower = error.lower()

        # Padrões conhecidos → lições pré-definidas
        if "triple" in error_lower or "unterminated string" in error_lower:
            return "CRÍTICO: Nunca usar triple-quotes para HTML/CSS/JS. Usar write_file ou base64."

        if "workspace/workspace" in error or "workspace/index" in error:
            return "CRÍTICO: Não usar prefixo workspace/ no path. Docker já está em /workspace."

        if "syntax" in error_lower and "f.write" in error:
            return "Evitar f.write() com strings longas. Usar write_file no JSON ou base64."

        if "oom" in error_lower or "137" in error or "memory" in error_lower:
            return "Tarefa usou muita RAM. Usar chunking ou reduzir escopo."

        if "timeout" in error_lower:
            return f"Tarefa excedeu timeout. Aumentar timeout ou dividir em subtarefas."

        if "not found" in error_lower or "no such file" in error_lower:
            return "Arquivo não encontrado. Verificar path relativo vs. absoluto."

        # Lição genérica para erros desconhecidos
        if strategy:
            return f"Estratégia '{strategy}' falhou com: {error[:100]}"

        return None


# ══════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM llm_client.py / agents.py
# ══════════════════════════════════════════════════════════════════
#
# Em generate_proposal() do llm_client.py, adicione após o SkillRouter:
#
#   from kosmos_memory import KosmosMemoryAdapter
#   if not hasattr(self, "_memory"):
#       self._memory = KosmosMemoryAdapter()
#
#   # Injeta lições aprendidas no prompt
#   _lesson_injection = self._memory.get_prompt_injection(task)
#   _active_prompt = SYSTEM_PROMPT_PROPOSER + _skill_protocol + _lesson_injection
#
# No Reflexion (reflexion.py), ao armazenar episódio:
#
#   from kosmos_memory import KosmosMemoryAdapter
#   _memory = KosmosMemoryAdapter()
#   _memory.store(task=task, success=success, error=error, strategy=strategy)


if __name__ == "__main__":
    import tempfile

    print("KosmosMemory — Demo\n")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name

    mem = KosmosMemory(db_path=db)

    # Popula com episódios de exemplo
    mem.store_episode(
        task="criar landing page para CNGSM",
        success=False,
        error="SyntaxError: triple-quotes",
        strategy="llm_generated",
        lesson="CRÍTICO: Usar write_file para HTML.",
    )
    mem.store_episode(
        task="criar site com dark theme",
        success=True,
        strategy="write_file",
        lesson="write_file funciona. Evitar Python com HTML.",
    )
    mem.store_episode(
        task="calcular fibonacci",
        success=True,
        strategy="python",
        lesson="Recursão simples funciona para n < 30.",
    )

    print(f"Episódios armazenados: {mem.count()}")
    print(f"Stats: {mem.get_stats()}")

    # Busca
    results = mem.search("landing page html site")
    print(f"\nBusca 'landing page html site': {len(results)} resultados")
    for r in results:
        print(f"  [{r['success']}] {r['task'][:50]} — {r.get('lesson','')[:60]}")

    # Injeção
    injection = mem.get_prompt_injection("preciso de uma landing page para empresa")
    print(f"\nInjeção para 'landing page empresa':")
    print(injection if injection else "  (nenhuma lição relevante)")

    Path(db).unlink(missing_ok=True)
    print("\n✓ Demo concluído")
