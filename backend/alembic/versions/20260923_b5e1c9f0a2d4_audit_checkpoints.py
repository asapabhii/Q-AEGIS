"""Add audit_signing_keys and audit_checkpoints for PQ-signed Signed Tree Heads.

Revision ID: b5e1c9f0a2d4
Revises: a3d8b1e4c907
Create Date: 2026-09-23

SPEC.md 3.8, PRD.md FR-7. These two tables turn the Merkle root the audit layer
recomputes into an externally verifiable commitment: audit_checkpoints stores
one ML-DSA-87-signed Signed Tree Head per issuance, and audit_signing_keys holds
the keypairs that sign them (public key in the clear for pinning, secret key
wrapped under CRYPTO_MASTER_KEY).

Both tables are append-only against UPDATE, DELETE, and TRUNCATE, held to the
same bar as audit_log: a checkpoint and the key that signed it are
tamper-evidence, and the anchoring guarantee is defeated the moment either can
be rewritten or quietly removed. The reject function
``qaegis_reject_append_only_write`` was created by the initial migration; this
migration only installs triggers that reference it, and drops those triggers
(never the shared function) on downgrade.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b5e1c9f0a2d4"
down_revision: Union[str, None] = "a3d8b1e4c907"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Shared reject function, created by the initial migration. Not recreated here.
REJECT_FUNCTION_NAME = "qaegis_reject_append_only_write"

# Both new tables reject UPDATE, DELETE, and TRUNCATE.
APPEND_ONLY_TABLES = ("audit_signing_keys", "audit_checkpoints")

#: Length of a hex-encoded SHA-256 Merkle root, matching audit_log.
HASH_HEX_LENGTH = 64


def _trigger_name(table: str, operation: str) -> str:
    """Return the trigger name for one table and operation (matches initial)."""
    return f"trg_{table}_no_{operation}"


def upgrade() -> None:
    op.create_table(
        "audit_signing_keys",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("wrapped_secret_key", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_signing_keys")),
    )
    op.create_index(
        op.f("ix_audit_signing_keys_created_at"),
        "audit_signing_keys",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "audit_checkpoints",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("signing_key_id", sa.Uuid(), nullable=False),
        sa.Column("tree_size", sa.Integer(), nullable=False),
        sa.Column("merkle_root", sa.CHAR(length=HASH_HEX_LENGTH), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column(
            "signed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_audit_checkpoints_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["signing_key_id"],
            ["audit_signing_keys.id"],
            name=op.f("fk_audit_checkpoints_signing_key_id_audit_signing_keys"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_checkpoints")),
    )
    op.create_index(
        op.f("ix_audit_checkpoints_document_id"),
        "audit_checkpoints",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_checkpoints_signing_key_id"),
        "audit_checkpoints",
        ["signing_key_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_checkpoints_signed_at"),
        "audit_checkpoints",
        ["signed_at"],
        unique=False,
    )

    _install_append_only_triggers()


def downgrade() -> None:
    _drop_append_only_triggers()

    op.drop_index(
        op.f("ix_audit_checkpoints_signed_at"), table_name="audit_checkpoints"
    )
    op.drop_index(
        op.f("ix_audit_checkpoints_signing_key_id"), table_name="audit_checkpoints"
    )
    op.drop_index(
        op.f("ix_audit_checkpoints_document_id"), table_name="audit_checkpoints"
    )
    op.drop_table("audit_checkpoints")

    op.drop_index(
        op.f("ix_audit_signing_keys_created_at"), table_name="audit_signing_keys"
    )
    op.drop_table("audit_signing_keys")


def _install_append_only_triggers() -> None:
    """Install UPDATE/DELETE/TRUNCATE guards on both tables.

    Reuses the reject function installed by the initial migration; it is not
    recreated here. TRUNCATE gets its own statement-level trigger because
    TRUNCATE does not fire row-level triggers, so a row-level DELETE guard alone
    would leave the whole table erasable in one statement.
    """
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {_trigger_name(table, 'update')} "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {REJECT_FUNCTION_NAME}();"
        )
        op.execute(
            f"CREATE TRIGGER {_trigger_name(table, 'delete')} "
            f"BEFORE DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {REJECT_FUNCTION_NAME}();"
        )
        op.execute(
            f"CREATE TRIGGER {_trigger_name(table, 'truncate')} "
            f"BEFORE TRUNCATE ON {table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION {REJECT_FUNCTION_NAME}();"
        )


def _drop_append_only_triggers() -> None:
    """Remove the guards so the tables can be dropped on downgrade.

    Drops only the triggers this migration created; the shared reject function
    is left in place because audit_log and the history tables still use it.
    """
    for table in APPEND_ONLY_TABLES:
        for operation in ("truncate", "delete", "update"):
            op.execute(
                f"DROP TRIGGER IF EXISTS {_trigger_name(table, operation)} "
                f"ON {table};"
            )
