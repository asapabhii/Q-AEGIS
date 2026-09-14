"""pgvector-backed chunk store for RAG, ``SPEC.md`` 3.12."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.rag.embeddings import EMBEDDING_MODEL_STUB, embed_text


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def upsert_chunk(
    session: Session,
    *,
    document_id: UUID | None,
    source_type: str,
    source_id: str | None,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    """Insert one chunk with a stub embedding. Returns the new chunk id."""
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
            "embedding_model": EMBEDDING_MODEL_STUB,
            "metadata": __import__("json").dumps(metadata or {}),
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
) -> list[dict[str, Any]]:
    """Return top-``limit`` chunks by cosine distance (pgvector ``<=>``)."""
    dims = get_settings().rag_embedding_dims
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
    return [
        {
            "chunk_id": row["id"],
            "document_id": row["document_id"],
            "source_type": row["source_type"],
            "source_id": row["source_id"],
            "content": row["content"],
            "embedding_model": row["embedding_model"],
            "score": float(row["score"] or 0.0),
        }
        for row in rows
    ]
