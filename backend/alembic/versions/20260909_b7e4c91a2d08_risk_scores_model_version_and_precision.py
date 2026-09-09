"""Add model_version to risk_scores and store risk_value at four decimal places.

Revision ID: b7e4c91a2d08
Revises: 3087697b7213
Create Date: 2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7e4c91a2d08"
down_revision: Union[str, None] = "3087697b7213"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "risk_scores",
        sa.Column(
            "model_version",
            sa.String(length=30),
            nullable=False,
            server_default="contextual-risk-additive-0.1.0",
        ),
    )
    op.alter_column("risk_scores", "model_version", server_default=None)
    op.alter_column(
        "risk_scores",
        "risk_value",
        existing_type=sa.Numeric(precision=4, scale=3),
        type_=sa.Numeric(precision=5, scale=4),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "risk_scores",
        "risk_value",
        existing_type=sa.Numeric(precision=5, scale=4),
        type_=sa.Numeric(precision=4, scale=3),
        existing_nullable=False,
    )
    op.drop_column("risk_scores", "model_version")
