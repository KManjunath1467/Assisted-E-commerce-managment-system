"""Database access layer for the customer support domain."""

import uuid as _uuid
from datetime import date

from db import get_session_factory
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.db_tables import tickets as _tickets


class CustomerSupportRepository:
    """Read-only queries against the tickets table."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def _execute(self, stmt):
        if self._session:
            result = await self._session.execute(stmt)
            return result
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(stmt)
            return result

    async def fetch_tickets_by_date(self, target: date) -> list[dict]:
        stmt = select(_tickets).where(_tickets.c.date == target)
        result = await self._execute(stmt)
        return [dict(r._mapping) for r in result.all()]

    async def fetch_ticket_by_id(self, ticket_id: _uuid.UUID) -> dict | None:
        stmt = select(_tickets).where(_tickets.c.id == ticket_id)
        result = await self._execute(stmt)
        row = result.first()
        return dict(row._mapping) if row else None

    async def fetch_recent_tickets(
        self,
        limit: int = 10,
        category: str = "",
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        stmt = select(_tickets).order_by(desc(_tickets.c.date))
        if category:
            stmt = stmt.where(_tickets.c.category == category)
        if date_from:
            stmt = stmt.where(_tickets.c.date >= date_from)
        if date_to:
            stmt = stmt.where(_tickets.c.date <= date_to)
        stmt = stmt.limit(limit)
        result = await self._execute(stmt)
        return [dict(r._mapping) for r in result.all()]
