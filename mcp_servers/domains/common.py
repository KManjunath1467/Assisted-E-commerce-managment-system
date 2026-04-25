"""Shared types used across all domains — single source of truth.

Both the MCP server and the backend import from here.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

# ── Enums ──────────────────────────────────────────────────────────────


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CampaignStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    SCHEDULED = "scheduled"


class Channel(str, Enum):
    EMAIL = "email"
    SOCIAL = "social"
    SEARCH = "search"
    DISPLAY = "display"
    AFFILIATE = "affiliate"


# ── Base models ────────────────────────────────────────────────────────


class TimeRange(BaseModel):
    start: datetime = Field(..., description="Start of the time range (UTC)")
    end: datetime = Field(..., description="End of the time range (UTC)")


class ProductRef(BaseModel):
    product_id: str = Field(..., description="Unique product identifier")
    name: str = Field(..., description="Product display name")
    category: str | None = Field(None, description="Product category")


def parse_date(d: str) -> date:
    """Parse a YYYY-MM-DD string into a date, with a user-friendly error message."""
    try:
        return date.fromisoformat(d)
    except ValueError:
        raise ValueError(
            f"Invalid date format: '{d}'. Expected YYYY-MM-DD (e.g. 2026-04-17)."
        )


async def resolve_product_ids(targets: list[str]) -> list[str]:
    """Resolve a mixed list of product IDs and product names to product IDs.

    Entries that already look like product IDs (exist in the products table)
    are kept as-is.  Entries that match a product name (case-insensitive) are
    mapped to the corresponding product_id.  Unrecognised entries are passed
    through unchanged so that callers that already supply valid IDs still work.
    """
    from db import get_session_factory
    from sqlalchemy import select

    from domains.db_tables import products

    factory = get_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(select(products.c.product_id, products.c.name))
        ).all()

    id_set = {r.product_id for r in rows}
    name_to_id = {r.name.lower(): r.product_id for r in rows}

    resolved: list[str] = []
    for t in targets:
        if t in id_set:
            resolved.append(t)
        elif t.lower() in name_to_id:
            resolved.append(name_to_id[t.lower()])
        else:
            # Pass through unrecognised values so pre-existing callers using
            # valid IDs that simply aren't in the products table still work.
            resolved.append(t)
    return resolved


async def resolve_product_labels(product_ids: list[str]) -> str:
    """Return a human-readable label string like 'Laptop Stand (PRD-003), Running Shoes (PRD-002)'."""
    from db import get_session_factory
    from sqlalchemy import select

    from domains.db_tables import products

    factory = get_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(select(products.c.product_id, products.c.name))
        ).all()

    id_to_name = {r.product_id: r.name for r in rows}
    labels = [f"{id_to_name.get(pid, pid)} ({pid})" for pid in product_ids]
    return ", ".join(labels)


async def resolve_campaign_labels(campaign_ids: list[str]) -> str:
    """Return a human-readable label string like 'Weekend Social Boost (camp-2)'."""
    from db import get_session_factory
    from sqlalchemy import select

    from domains.db_tables import campaigns

    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(campaigns.c.id, campaigns.c.name))).all()

    id_to_name = {str(r.id): r.name for r in rows}
    labels = [f"{id_to_name.get(cid, cid)} ({cid})" for cid in campaign_ids]
    return ", ".join(labels)


class Anomaly(BaseModel):
    metric: str = Field(..., description="Name of the anomalous metric")
    expected: float = Field(
        ..., description="Expected value based on historical baseline"
    )
    actual: float = Field(..., description="Observed actual value")
    deviation_pct: float = Field(
        ..., description="Percentage deviation from expected (negative = below)"
    )
    severity: Severity = Field(
        ..., description="Severity classification of the anomaly"
    )
