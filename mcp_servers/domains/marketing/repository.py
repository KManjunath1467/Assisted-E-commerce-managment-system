"""Database access layer for the marketing domain."""

from db import get_session_factory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.db_tables import campaigns as _campaigns


class MarketingRepository:
    """Read-only queries against the campaigns table."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def fetch_campaigns(self) -> list[dict]:
        if self._session:
            result = await self._session.execute(select(_campaigns))
            return [dict(r._mapping) for r in result.all()]
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(_campaigns))
            return [dict(r._mapping) for r in result.all()]
