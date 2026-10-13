"""``rag_chunks`` — pgvector store for FR-11 agentic RAG (``SPEC.md`` 3.12).

Not one of the twelve core domain tables. See ``docs/data-dictionary.md``.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, uuid_primary_key


class RagChunk(Base):
    """One embedded text chunk used by the Verifier-backed ask pipeline.

    ``embedding_model`` records which model produced the vector (e.g.
    ``BAAI/bge-large-en-v1.5`` in production, or ``deterministic-hash-v1`` for
    hermetic tests) so a re-embed can be detected and no query mixes incompatible
    vector spaces. The column width must match ``RAG_EMBEDDING_DIMS``.
    """

    __tablename__ = "rag_chunks"

    __table_args__ = (
        # HNSW cosine index matching the '<=>' ordering in similarity_search.
        # Declared on the model (not only in the migration) so the model-vs-DB
        # drift check sees it. Keep in sync with the rag_embeddings_1024_hnsw
        # migration.
        Index(
            "ix_rag_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID | None] = mapped_column(
        # ON DELETE CASCADE (not RESTRICT like the evidence/decision tables) is
        # intentional: chunks are derived, re-ingestable data, not evidence, so
        # deleting a document should drop its stale embeddings automatically.
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(80), nullable=False)
    # Column name matches the migration / data-dictionary; ``metadata`` is
    # reserved on DeclarativeBase.
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = created_timestamp()
