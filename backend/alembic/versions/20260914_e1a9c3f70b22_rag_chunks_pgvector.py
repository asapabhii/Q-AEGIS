"""Add rag_chunks + pgvector for FR-11 agentic RAG.

Revision ID: e1a9c3f70b22
Revises: c4f8a1e92b03
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e1a9c3f70b22"
down_revision: Union[str, None] = "c4f8a1e92b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE rag_chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id uuid REFERENCES documents(id) ON DELETE CASCADE,
            source_type varchar(80) NOT NULL,
            source_id varchar(120),
            content text NOT NULL,
            embedding vector(64) NOT NULL,
            embedding_model varchar(80) NOT NULL,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_rag_chunks_document_id ON rag_chunks (document_id)")
    op.execute("CREATE INDEX ix_rag_chunks_source_type ON rag_chunks (source_type)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rag_chunks")
