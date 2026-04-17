"""add products table

Revision ID: c1d2e3f4a5b6
Revises: b7e2d3f4a1c5
Create Date: 2026-04-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b7e2d3f4a1c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create products table
    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )

    # 2. Clear inventory-dependent data so FK constraints can be applied cleanly.
    #    The seed script repopulates all rows after migration.
    op.execute("DELETE FROM sales")
    op.execute("DELETE FROM inventory")

    # 3. Drop the FK on sales.product_id that pointed to inventory.product_id
    op.drop_constraint("sales_product_id_fkey", "sales", type_="foreignkey")

    # 4. Remove product_name from inventory
    op.drop_column("inventory", "product_name")

    # 5. Add FK on inventory.product_id -> products.product_id
    op.create_foreign_key(
        "inventory_product_id_fkey",
        "inventory",
        "products",
        ["product_id"],
        ["product_id"],
    )

    # 6. Add FK on sales.product_id -> products.product_id
    op.create_foreign_key(
        "sales_product_id_fkey",
        "sales",
        "products",
        ["product_id"],
        ["product_id"],
    )


def downgrade() -> None:
    # 1. Drop FKs added in upgrade
    op.drop_constraint("sales_product_id_fkey", "sales", type_="foreignkey")
    op.drop_constraint("inventory_product_id_fkey", "inventory", type_="foreignkey")

    # 2. Re-add product_name to inventory (nullable so downgrade doesn't fail on existing rows)
    op.add_column(
        "inventory",
        sa.Column("product_name", sa.String(), nullable=True),
    )

    # 3. Re-add original FK on sales.product_id -> inventory.product_id
    op.create_foreign_key(
        "sales_product_id_fkey",
        "sales",
        "inventory",
        ["product_id"],
        ["product_id"],
    )

    # 4. Drop products table
    op.drop_table("products")
