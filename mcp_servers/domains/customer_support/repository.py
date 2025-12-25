"""Database access layer for the customer support domain."""

from datetime import date

from db import get_session_factory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.db_tables import tickets as _tickets


class CustomerSupportRepository:
    """Read-only queries against the tickets table."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def fetch_tickets_by_date(self, target: date) -> list[dict]:
        stmt = select(_tickets).where(_tickets.c.date == target)
        if self._session:
            result = await self._session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(stmt)
            return [dict(r._mapping) for r in result.all()]
