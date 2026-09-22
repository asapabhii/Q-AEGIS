"""Widen rag_chunks.embedding to 1024 dims and add an HNSW cosine index.

FR-11 moves from the 64-dim deterministic hash embedding to real transformer
embeddings (default BAAI/bge-large-en-v1.5, 1024-dim). The stored vectors are
derived from Postgres decision records and are re-ingested from source, so the
column can be cleared and rebuilt rather than back-filled: a 64-dim vector cannot
be cast into a 1024-dim space meaningfully, and mixing widths in one column is a
query error waiting to happen.

The HNSW index on ``vector_cosine_ops`` matches the ``<=>`` cosine ordering the
similarity search uses, so retrieval stays fast as the store grows instead of
falling back to a sequential scan.

Revision ID: f2c7a9d15e30
Revises: e1a9c3f70b22
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f2c7a9d15e30"
down_revision: Union[str, None] = "e1a9c3f70b22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Derived vectors: clear and re-ingest rather than back-fill. A 64-dim hash
    # vector has no meaningful 1024-dim image, so keeping the rows would poison
    # every similarity query until they were overwritten anyway.
    op.execute("DELETE FROM rag_chunks")
    op.execute(
        "ALTER TABLE rag_chunks "
        "ALTER COLUMN embedding TYPE vector(1024) "
        "USING embedding::vector(1024)"
    )
    # Cosine HNSW index to match the '<=>' ordering in similarity_search.
    op.execute(
        "CREATE INDEX ix_rag_chunks_embedding_hnsw "
        "ON rag_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_hnsw")
    op.execute("DELETE FROM rag_chunks")
    op.execute(
        "ALTER TABLE rag_chunks "
        "ALTER COLUMN embedding TYPE vector(64) "
        "USING embedding::vector(64)"
    )
