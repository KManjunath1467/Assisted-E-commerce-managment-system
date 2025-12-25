"""Database access layer for the marketing domain."""

from db import get_session_factory
from sqlalchemy import Column, MetaData, String, Table, select
from sqlalchemy.dialects.postgresql import JSONB

_meta = MetaData()

_campaigns = Table(
    "campaigns",
    _meta,
    Column("id", String, key="id"),
    Column("name", String, key="name"),
    Column("channel", String, key="channel"),
    Column("status", String, key="status"),
    Column("performance", JSONB, key="performance"),
)


class MarketingRepository:
    """Read-only queries against the campaigns table."""

    async def fetch_campaigns(self) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(select(_campaigns))
            return [dict(r._mapping) for r in result.all()]
