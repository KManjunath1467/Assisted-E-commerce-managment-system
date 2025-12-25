"""add thread_id to actions

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-04-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "actions",
        sa.Column("thread_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_actions_thread_id",
        "actions",
        "threads",
        ["thread_id"],
        ["thread_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_actions_thread_id", "actions", type_="foreignkey")
    op.drop_column("actions", "thread_id")
