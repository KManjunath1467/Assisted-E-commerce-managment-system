"""Database access layer for the inventory domain."""

from datetime import date

from db import get_session_factory
from sqlalchemy import Column, Date, Integer, MetaData, Numeric, String, Table, select

_meta = MetaData()

_products = Table(
    "products",
    _meta,
    Column("product_id", String, key="product_id"),
    Column("name", String, key="name"),
    Column("category", String, key="category"),
    Column("unit_price", Numeric(10, 2), key="unit_price"),
)

_inventory = Table(
    "inventory",
    _meta,
    Column("product_id", String, key="product_id"),
    Column("stock", Integer, key="stock"),
)

_sales = Table(
    "sales",
    _meta,
    Column("date", Date, key="date"),
    Column("product_id", String, key="product_id"),
    Column("revenue", Numeric(12, 2), key="revenue"),
    Column("quantity", Integer, key="quantity"),
    Column("region", String, key="region"),
)


class InventoryRepository:
    """Read-only queries against inventory, products, and sales tables."""

    async def fetch_inventory(self) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(_inventory))
            return [dict(r._mapping) for r in result.all()]

    async def fetch_products(self) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(_products))
            return [dict(r._mapping) for r in result.all()]

    async def fetch_sales_by_date_range(self, start: date, end: date) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(_sales).where(_sales.c.date >= start, _sales.c.date < end)
            result = await session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]
