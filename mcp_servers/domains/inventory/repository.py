"""Database access layer for the inventory domain."""

from datetime import date

from db import get_session_factory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.db_tables import inventory as _inventory, products as _products, sales as _sales


class InventoryRepository:
    """Read-only queries against inventory, products, and sales tables."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def fetch_inventory(self) -> list[dict]:
        if self._session:
            result = await self._session.execute(select(_inventory))
            return [dict(r._mapping) for r in result.all()]
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(_inventory))
            return [dict(r._mapping) for r in result.all()]

    async def fetch_products(self) -> list[dict]:
        if self._session:
            result = await self._session.execute(select(_products))
            return [dict(r._mapping) for r in result.all()]
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(_products))
            return [dict(r._mapping) for r in result.all()]

    async def fetch_sales_by_date_range(self, start: date, end: date) -> list[dict]:
        stmt = select(_sales).where(_sales.c.date >= start, _sales.c.date <= end)
        if self._session:
            result = await self._session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]
