"""Stage 3 — local embedding model (fastembed / ONNX, CPU-only, no Claude).

The model (~650 MB resident) is loaded lazily and cached as a module-level
singleton, so importing this module is cheap and the model only loads the first
time we actually embed something. Vectors are L2-normalized on the way out, so
cosine similarity reduces to a dot product at search time.
"""

from __future__ import annotations

import numpy as np

from backend.config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts into an (n, dim) float32 array of unit vectors."""
    if not texts:
        return np.zeros((0, settings.embedding_dim), dtype=np.float32)
    vecs = np.array(list(_get_model().embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # guard against zero vectors
    return vecs / norms
