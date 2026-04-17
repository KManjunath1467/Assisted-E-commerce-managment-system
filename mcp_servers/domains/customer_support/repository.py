"""Database access layer for the customer support domain."""

from datetime import date

from db import get_session_factory
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    MetaData,
    String,
    Table,
    Text,
    select,
)

_meta = MetaData()

_tickets = Table(
    "tickets",
    _meta,
    Column("id", String, key="id"),
    Column("date", Date, key="date"),
    Column("category", String, key="category"),
    Column("sentiment_score", Float, key="sentiment_score"),
    Column("is_refund", Boolean, key="is_refund"),
    Column("is_return", Boolean, key="is_return"),
    Column("review_text", Text, key="review_text"),
)


class CustomerSupportRepository:
    """Read-only queries against the tickets table."""

    async def fetch_tickets_by_date(self, target: date) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(_tickets).where(_tickets.c.date == target)
            )
            return [dict(r._mapping) for r in result.all()]
