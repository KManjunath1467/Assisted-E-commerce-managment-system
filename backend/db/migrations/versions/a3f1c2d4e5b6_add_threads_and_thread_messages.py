"""add threads and thread_messages tables

Revision ID: a3f1c2d4e5b6
Revises: 29b4eaec2f74
Create Date: 2026-04-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3f1c2d4e5b6"
down_revision: str | None = "29b4eaec2f74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "threads",
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("thread_id"),
    )
    op.create_index("ix_threads_updated_at", "threads", ["updated_at"], unique=False)

    op.create_table(
        "thread_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.thread_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_thread_messages_thread_id",
        "thread_messages",
        ["thread_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_thread_messages_thread_id", table_name="thread_messages")
    op.drop_table("thread_messages")
    op.drop_index("ix_threads_updated_at", table_name="threads")
    op.drop_table("threads")
