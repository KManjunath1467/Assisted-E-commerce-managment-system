"""add tickets table

Revision ID: b7e2d3f4a1c5
Revises: a3f1c2d4e5b6
Create Date: 2026-04-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2d3f4a1c5"
down_revision: str | None = "a3f1c2d4e5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_refund", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_return", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("review_text", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_date", "tickets", ["date"], unique=False)
    op.create_index("ix_tickets_category", "tickets", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tickets_category", table_name="tickets")
    op.drop_index("ix_tickets_date", table_name="tickets")
    op.drop_table("tickets")
