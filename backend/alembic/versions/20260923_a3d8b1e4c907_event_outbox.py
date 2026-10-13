"""Add event_outbox for the durable transactional outbox.

Revision ID: a3d8b1e4c907
Revises: f2c7a9d15e30
Create Date: 2026-09-23

Backs the transactional-outbox pattern (SPEC.md 3.1): domain writes enqueue their
events into this table in the same transaction, and app.event_bus.relay drains
committed rows to Redis Streams. Not append-only — the relay UPDATEs status as a
row moves pending -> sent, or pending -> dead after exhausting retries — so no
reject-UPDATE trigger is installed here.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a3d8b1e4c907"
down_revision: Union[str, None] = "f2c7a9d15e30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_outbox",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("stream_id", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'dead')",
            name=op.f("ck_event_outbox_valid_status"),
        ),
        sa.CheckConstraint(
            "attempts >= 0", name=op.f("ck_event_outbox_attempts_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_outbox")),
    )
    op.create_index(
        op.f("ix_event_outbox_status"), "event_outbox", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_event_outbox_created_at"),
        "event_outbox",
        ["created_at"],
        unique=False,
    )
    # Partial index serving the relay's hot "due pending rows, oldest first"
    # query. Restricted to pending rows so sent/dead history never bloats it.
    op.create_index(
        "ix_event_outbox_due",
        "event_outbox",
        ["next_attempt_at", "created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_event_outbox_due", table_name="event_outbox")
    op.drop_index(op.f("ix_event_outbox_created_at"), table_name="event_outbox")
    op.drop_index(op.f("ix_event_outbox_status"), table_name="event_outbox")
    op.drop_table("event_outbox")
