"""Market Knowledge Base — retrieval over everything the agent has learned.

Every research finding (across all leads and all runs) is stored here, so the
agent builds compounding market knowledge: "what do we know about dental
clinics in Austin?" becomes answerable after a few runs.

Implementation: a small TF-IDF vector store built from scratch (pure Python,
zero dependencies). Documents and queries become sparse vectors; similarity is
cosine. This is exactly what "real" vector databases do, minus the neural
embeddings — and because the interface is 3 methods (add / search / count),
you can swap in ChromaDB or Qdrant later without touching the rest of the app.

Why from scratch? (a) it teaches the mechanics, (b) it has zero install risk,
(c) at this corpus size TF-IDF retrieval is genuinely competitive.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from pathlib import Path

DB_PATH = Path("knowledge_base.db")

_WORD_RE = re.compile(r"[a-z0-9]+")

# Common words that carry no meaning for retrieval.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "is",
    "are", "was", "were", "with", "by", "from", "as", "it", "its", "this",
    "that", "be", "has", "have", "had", "their", "they", "we", "our", "you",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase -> words -> drop stopwords."""
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS]


class KnowledgeBase:
    """A persistent mini vector store (TF-IDF + cosine similarity) on SQLite."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                text     TEXT NOT NULL,
                source   TEXT NOT NULL,
                lead     TEXT NOT NULL,
                location TEXT NOT NULL,
                tokens   TEXT NOT NULL      -- JSON list of tokens (cached)
            )
            """
        )
        self._conn.commit()

    # ---------- write ----------

    def add(self, text: str, source: str, lead: str, location: str) -> None:
        """Store one finding (skips exact duplicates)."""
        exists = self._conn.execute(
            "SELECT 1 FROM documents WHERE text = ? AND lead = ?", (text, lead)
        ).fetchone()
        if exists:
            return
        self._conn.execute(
            "INSERT INTO documents (text, source, lead, location, tokens) VALUES (?, ?, ?, ?, ?)",
            (text, source, lead, location, json.dumps(_tokenize(text))),
        )
        self._conn.commit()

    # ---------- read ----------

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def search(self, query: str, k: int = 5) -> list[dict]:
        """TF-IDF cosine similarity search. Returns top-k docs with scores."""
        rows = self._conn.execute(
            "SELECT text, source, lead, location, tokens FROM documents"
        ).fetchall()
        if not rows:
            return []

        docs = [json.loads(row[4]) for row in rows]
        n_docs = len(docs)

        # IDF: rare-across-documents words matter more.
        document_frequency: Counter = Counter()
        for tokens in docs:
            document_frequency.update(set(tokens))

        def idf(term: str) -> float:
            return math.log((n_docs + 1) / (document_frequency.get(term, 0) + 1)) + 1.0

        def vectorize(tokens: list[str]) -> dict[str, float]:
            counts = Counter(tokens)
            total = max(len(tokens), 1)
            return {term: (count / total) * idf(term) for term, count in counts.items()}

        def cosine(a: dict[str, float], b: dict[str, float]) -> float:
            shared = set(a) & set(b)
            dot = sum(a[t] * b[t] for t in shared)
            norm_a = math.sqrt(sum(v * v for v in a.values()))
            norm_b = math.sqrt(sum(v * v for v in b.values()))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        query_vec = vectorize(_tokenize(query))
        scored = []
        for row, tokens in zip(rows, docs):
            score = cosine(query_vec, vectorize(tokens))
            if score > 0:
                scored.append(
                    {
                        "text": row[0],
                        "source": row[1],
                        "lead": row[2],
                        "location": row[3],
                        "score": round(score, 4),
                    }
                )
        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:k]

    def close(self) -> None:
        self._conn.close()
