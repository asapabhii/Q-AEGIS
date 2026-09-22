"""Semantic embeddings for RAG, ``SPEC.md`` 3.12 / ``PRD.md`` FR-11.

Two backends, selected by ``RAG_EMBEDDING_BACKEND``:

- ``fastembed`` (default, production): real transformer embeddings via
  ``fastembed`` (ONNX Runtime, no PyTorch). The default model is
  ``BAAI/bge-large-en-v1.5`` (1024-dim), a strong CPU-deployable retrieval model.
  The model is downloaded once and cached on disk; runs fully offline afterward.
  No external API and no API key.
- ``deterministic`` (tests / air-gapped smoke only): a hash-based vector that is
  stable across processes but carries NO semantic meaning. It exists so the test
  suite and CI stay hermetic and fast without downloading a model. It must never
  be the production backend; ``app.config`` defaults to ``fastembed``.

Whichever backend is active, embeddings are L2-normalized and their width must
equal ``RAG_EMBEDDING_DIMS`` (which must match the ``rag_chunks.embedding``
pgvector column). A mismatch is raised, not silently truncated.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

from app.config import get_settings

#: Model id recorded for the deterministic backend. The ``fastembed`` backend
#: records the real model name (e.g. ``BAAI/bge-large-en-v1.5``) instead.
DETERMINISTIC_MODEL_NAME = "deterministic-hash-v1"

BACKEND_FASTEMBED = "fastembed"
BACKEND_DETERMINISTIC = "deterministic"


def embedding_model_name() -> str:
    """Return the model id to record on chunks and API responses."""
    settings = get_settings()
    if settings.rag_embedding_backend == BACKEND_DETERMINISTIC:
        return DETERMINISTIC_MODEL_NAME
    return settings.rag_embedding_model


@lru_cache(maxsize=4)
def _fastembed_model(model_name: str):
    """Load (and cache) one fastembed model. First call downloads the weights.

    Imported lazily so environments that only use the deterministic backend
    (and CI jobs that have not installed fastembed) do not pay the import cost.
    """
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model_name)


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _deterministic_embed(text: str, dims: int) -> list[float]:
    """Stable, non-semantic hash embedding for tests / air-gapped runs.

    Bag-of-token SHA-256 contributions mixed into each dimension. Deterministic
    across processes; NOT a semantic model. See the module docstring.
    """
    if dims < 8:
        raise ValueError("dims must be >= 8")
    vec = [0.0] * dims
    tokens = re.findall(r"[a-z0-9_]+", text.lower()) or ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(dims):
            b0 = digest[i % len(digest)]
            b1 = digest[(i * 7 + 3) % len(digest)]
            vec[i] += ((b0 / 255.0) * 2.0 - 1.0) + ((b1 / 255.0) - 0.5)
    return _l2_normalize(vec)


def _fastembed_embed(text: str, model_name: str, expected_dims: int) -> list[float]:
    """Real embedding via fastembed, validated to the configured width."""
    model = _fastembed_model(model_name)
    vector = next(iter(model.embed([text])))
    values = [float(v) for v in vector.tolist()]
    if len(values) != expected_dims:
        raise ValueError(
            f"Embedding model {model_name!r} produced {len(values)} dimensions, "
            f"but RAG_EMBEDDING_DIMS is {expected_dims}. Align the setting (and the "
            "rag_chunks.embedding column) with the model's native dimension."
        )
    return _l2_normalize(values)


def embed_text(text: str, *, dims: int | None = None) -> list[float]:
    """Return an L2-normalized embedding for ``text`` using the active backend.

    ``dims`` overrides the configured width for the deterministic backend only
    (tests pin it); the fastembed backend's width is fixed by the model and is
    checked against ``RAG_EMBEDDING_DIMS``.
    """
    settings = get_settings()
    width = dims if dims is not None else settings.rag_embedding_dims
    if settings.rag_embedding_backend == BACKEND_DETERMINISTIC:
        return _deterministic_embed(text, width)
    return _fastembed_embed(text, settings.rag_embedding_model, width)
