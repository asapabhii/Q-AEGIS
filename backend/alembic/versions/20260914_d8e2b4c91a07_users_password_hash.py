"""Add ``users.password_hash`` for local JWT auth.

Revision ID: d8e2b4c91a07
Revises: c4f8a1e92b03
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8e2b4c91a07"
down_revision: Union[str, None] = "c4f8a1e92b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_hash")
