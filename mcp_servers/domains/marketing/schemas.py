"""Pydantic models for the marketing domain."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from domains.common import CampaignStatus, Channel


class CampaignMetrics(BaseModel):
    spend: float = Field(..., description="Total ad spend")
    impressions: int = Field(..., description="Total impressions")
    clicks: int = Field(..., description="Total clicks")
    conversions: int = Field(..., description="Total conversions")
    roas: float = Field(..., description="Return on ad spend (revenue / spend)")


class Campaign(BaseModel):
    campaign_id: str = Field(..., description="Unique campaign identifier")
    name: str = Field(..., description="Campaign display name")
    channel: Channel = Field(..., description="Marketing channel")
    status: CampaignStatus = Field(..., description="Current campaign status")
    current_period: CampaignMetrics = Field(
        ..., description="Metrics for the current analysis period"
    )
    previous_period: CampaignMetrics | None = Field(
        None, description="Metrics from the comparison period"
    )
    start_date: date = Field(..., description="Campaign start date")
    end_date: date | None = Field(
        None, description="Campaign end date (None if ongoing)"
    )


class MarketingAnalysis(BaseModel):
    kind: Literal["marketing"]
    campaigns: list[Campaign] = Field(
        default_factory=list,
        description="All campaigns in the analysis period",
    )
    underperforming: list[Campaign] = Field(
        default_factory=list,
        description="Campaigns performing below expected thresholds",
    )
    worst_channel: Channel | None = Field(
        None, description="Channel with the worst performance in the period"
    )
    insights: list[str] = Field(
        default_factory=list,
        description="Human-readable insights from the marketing analysis",
    )
