"""Shared types used across all domains — single source of truth.

Both the MCP server and the backend import from here.
"""

from datetime import datetime
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
