"""``rag_chunks`` — pgvector store for FR-11 agentic RAG (``SPEC.md`` 3.12).

Not one of the twelve core domain tables. See ``docs/data-dictionary.md``.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, uuid_primary_key


class RagChunk(Base):
    """One embedded text chunk used by the Verifier-backed ask pipeline.

    Embeddings in this phase are the labelled stub ``stub-hash-v1``; the
    ``embedding_model`` column records that so a real embedder can be swapped
    without silent incompatibility.
    """

    __tablename__ = "rag_chunks"

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(64), nullable=False)
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
