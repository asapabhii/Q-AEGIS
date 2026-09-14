"""Deterministic local embedding stub for RAG, ``SPEC.md`` 3.12.

THIS IS A STUB. It hashes tokens into a fixed-width float vector so pgvector
retrieval and the four-node LangGraph pipeline can be tested without a remote
embedding API. Do not describe it as a production semantic model. Replace with
a real embedder when a labelled embedding path exists (PRD §9 analogue).
"""

from __future__ import annotations

import hashlib
import math
import re

from app.config import get_settings

#: Public name written into ``rag_chunks.embedding_model`` and API responses.
EMBEDDING_MODEL_STUB = "stub-hash-v1"


def embed_text(text: str, *, dims: int | None = None) -> list[float]:
    """Return an L2-normalized ``dims``-vector for ``text``.

    Stub algorithm: bag-of-token SHA-256 contributions mixed into each
    dimension. Stable across processes; not semantically meaningful.
    """
    width = dims if dims is not None else get_settings().rag_embedding_dims
    if width < 8:
        raise ValueError("dims must be >= 8")
    vec = [0.0] * width
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    if not tokens:
        tokens = ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(width):
            # Mix two bytes per dimension for slightly less sparse vectors.
            b0 = digest[i % len(digest)]
            b1 = digest[(i * 7 + 3) % len(digest)]
            vec[i] += ((b0 / 255.0) * 2.0 - 1.0) + ((b1 / 255.0) - 0.5)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
