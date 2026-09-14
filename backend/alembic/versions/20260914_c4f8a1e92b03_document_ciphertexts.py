"""Add document_ciphertexts for stored ciphertext and wrapped DEKs.

Revision ID: c4f8a1e92b03
Revises: b7e4c91a2d08
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4f8a1e92b03"
down_revision: Union[str, None] = "b7e4c91a2d08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_ciphertexts",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("crypto_profile_id", sa.Uuid(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=False),
        sa.Column("kem_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("algorithm", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["crypto_profile_id"],
            ["crypto_profiles.id"],
            name=op.f("fk_document_ciphertexts_crypto_profile_id_crypto_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_ciphertexts_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_ciphertexts")),
    )
    op.create_index(
        op.f("ix_document_ciphertexts_created_at"),
        "document_ciphertexts",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_ciphertexts_crypto_profile_id"),
        "document_ciphertexts",
        ["crypto_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_ciphertexts_document_id"),
        "document_ciphertexts",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_ciphertexts_document_id"), table_name="document_ciphertexts"
    )
    op.drop_index(
        op.f("ix_document_ciphertexts_crypto_profile_id"),
        table_name="document_ciphertexts",
    )
    op.drop_index(
        op.f("ix_document_ciphertexts_created_at"), table_name="document_ciphertexts"
    )
    op.drop_table("document_ciphertexts")
