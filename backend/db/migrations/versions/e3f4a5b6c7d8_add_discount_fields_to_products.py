"""add discount fields to products

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-04-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("discount_pct", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "products",
        sa.Column(
            "discount_active", sa.Boolean(), nullable=False, server_default="false"
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "discount_active")
    op.drop_column("products", "discount_pct")
