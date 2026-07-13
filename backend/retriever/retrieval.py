"""Stage 3 — build embeddings for laws and run similarity search.

Retrieval is NumPy brute-force cosine similarity over the whole (small) corpus:
at this scale (tens to a couple hundred articles) a separate vector DB would be
pure overhead. Vectors are stored normalized, so cosine == dot product.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select

from backend.config import settings
from backend.db import Law, session_scope
from backend.retriever.embedder import embed_texts


@dataclass
class RetrievedLaw:
    law_id: int
    title: str
    chapter: str | None
    page: int | None
    text: str
    keywords: list[str]
    score: float


def embed_pending_laws() -> int:
    """Embed every law whose `embedding` is still empty. Returns count embedded."""
    with session_scope() as session:
        laws = session.scalars(select(Law)).all()
        pending = [law for law in laws if not law.embedding]
        if not pending:
            return 0
        vectors = embed_texts([law.text for law in pending])
        for law, vec in zip(pending, vectors):
            law.embedding = vec.tolist()
        return len(pending)


def reembed_all_laws() -> int:
    """Recompute embeddings for all laws (use after changing the model). Returns count."""
    with session_scope() as session:
        laws = session.scalars(select(Law)).all()
        if not laws:
            return 0
        vectors = embed_texts([law.text for law in laws])
        for law, vec in zip(laws, vectors):
            law.embedding = vec.tolist()
        return len(laws)


def search(query: str, top_k: int | None = None) -> list[RetrievedLaw]:
    """Return the top-k laws most similar to `query`, highest score first."""
    top_k = top_k or settings.top_k
    with session_scope() as session:
        laws = session.scalars(select(Law)).all()
        embedded = [law for law in laws if law.embedding]
        if not embedded:
            return []

        matrix = np.array([law.embedding for law in embedded], dtype=np.float32)
        q = embed_texts([query])[0]  # already unit-normalized
        scores = matrix @ q  # cosine similarity (both sides normalized)

        order = np.argsort(-scores)[:top_k]
        return [
            RetrievedLaw(
                law_id=embedded[i].law_id,
                title=embedded[i].title,
                chapter=embedded[i].chapter,
                page=embedded[i].page,
                text=embedded[i].text,
                keywords=embedded[i].keywords or [],
                score=float(scores[i]),
            )
            for i in order
        ]
