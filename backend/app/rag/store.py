"""pgvector-backed chunk store for RAG, ``SPEC.md`` 3.12."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.rag.embeddings import embed_text, embedding_model_name


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def effective_min_similarity(settings=None) -> float:
    """Similarity floor that actually applies given the active backend.

    The floor is a *semantic* relevance gate: it only carries meaning when the
    embeddings encode semantics, i.e. the real ``fastembed`` backend. The
    deterministic hash backend (tests / air-gapped smoke) produces non-semantic
    vectors whose cosine scores are noise, so a floor there would reject valid
    fixtures for no signal. Return the configured floor for ``fastembed`` and
    ``0.0`` (disabled) otherwise. Both the retriever and the Verifier use this so
    the "refuse if ungrounded" decision is computed one way.
    """
    settings = settings or get_settings()
    if settings.rag_embedding_backend == "fastembed":
        return float(settings.rag_min_similarity)
    return 0.0


def upsert_chunk(
    session: Session,
    *,
    document_id: UUID | None,
    source_type: str,
    source_id: str | None,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    """Embed ``content`` with the active backend and insert one chunk.

    The embedding comes from :func:`app.rag.embeddings.embed_text` (real
    fastembed transformer vectors in production; the deterministic hash backend
    only under tests / air-gapped smoke). Returns the new chunk id.
    """
    dims = get_settings().rag_embedding_dims
    embedding = embed_text(content, dims=dims)
    chunk_id = uuid4()
    session.execute(
        text("""
            INSERT INTO rag_chunks (
                id, document_id, source_type, source_id, content,
                embedding, embedding_model, metadata
            ) VALUES (
                :id, :document_id, :source_type, :source_id, :content,
                CAST(:embedding AS vector), :embedding_model,
                CAST(:metadata AS jsonb)
            )
            """),
        {
            "id": str(chunk_id),
            "document_id": str(document_id) if document_id else None,
            "source_type": source_type,
            "source_id": source_id,
            "content": content,
            "embedding": _vector_literal(embedding),
            "embedding_model": embedding_model_name(),
            "metadata": json.dumps(metadata or {}),
        },
    )
    return chunk_id


def delete_chunks_for_document(session: Session, document_id: UUID) -> int:
    """Remove prior chunks for a document before re-ingest."""
    result = session.execute(
        text("DELETE FROM rag_chunks WHERE document_id = :document_id"),
        {"document_id": str(document_id)},
    )
    return int(result.rowcount or 0)


def similarity_search(
    session: Session,
    query: str,
    *,
    document_id: UUID | None = None,
    limit: int = 5,
    min_similarity: float | None = None,
) -> list[dict[str, Any]]:
    """Return the top-``limit`` chunks that clear the similarity floor.

    Chunks are ranked by cosine distance (pgvector ``<=>``) and then filtered to
    those whose cosine similarity (``1 - distance``) is at least
    ``min_similarity``. When ``min_similarity`` is ``None`` the backend-aware
    :func:`effective_min_similarity` floor applies. An empty result means nothing
    stored is relevant enough to ground an answer, which the Verifier turns into
    a refusal rather than answering from noise.
    """
    settings = get_settings()
    dims = settings.rag_embedding_dims
    if min_similarity is None:
        min_similarity = effective_min_similarity(settings)
    embedding = embed_text(query, dims=dims)
    params: dict[str, Any] = {
        "embedding": _vector_literal(embedding),
        "limit": limit,
    }
    doc_clause = ""
    if document_id is not None:
        doc_clause = "AND document_id = :document_id"
        params["document_id"] = str(document_id)
    rows = session.execute(
        text(f"""
            SELECT id, document_id, source_type, source_id, content,
                   embedding_model,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM rag_chunks
            WHERE true {doc_clause}
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """),
        params,
    ).mappings()
    results: list[dict[str, Any]] = []
    for row in rows:
        score = float(row["score"] or 0.0)
        if score < min_similarity:
            # Ranked by distance, so once one row is below the floor the rest
            # are too; skip it and keep scanning defensively rather than break
            # (float ties near the floor should not silently drop a valid row).
            continue
        results.append(
            {
                "chunk_id": row["id"],
                "document_id": row["document_id"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "content": row["content"],
                "embedding_model": row["embedding_model"],
                "score": score,
            }
        )
    return results
