"""Widen model_version columns from 30 to 64 characters.

The classifier's real trained-artifact version
("wikileaks-cables-hashing-svm-1.0.0", 34 chars) overflows the original
VARCHAR(30) on classification_metadata.model_version and fails the classify
write closed with StringDataRightTruncation. risk_scores.model_version is
widened in step: its current value ("contextual-risk-additive-0.1.0") is
already exactly 30 characters, so any longer scorer version would overflow too.

Revision ID: c7f2a4e9d1b6
Revises: b5e1c9f0a2d4
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7f2a4e9d1b6"
down_revision: Union[str, None] = "b5e1c9f0a2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "classification_metadata",
        "model_version",
        existing_type=sa.String(length=30),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "risk_scores",
        "model_version",
        existing_type=sa.String(length=30),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Narrowing back to 30 truncates any value longer than 30 characters, which
    # is exactly the trained-artifact version this migration exists to store.
    op.alter_column(
        "risk_scores",
        "model_version",
        existing_type=sa.String(length=64),
        type_=sa.String(length=30),
        existing_nullable=False,
    )
    op.alter_column(
        "classification_metadata",
        "model_version",
        existing_type=sa.String(length=64),
        type_=sa.String(length=30),
        existing_nullable=False,
    )
