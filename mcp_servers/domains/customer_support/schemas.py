"""Pydantic models for the customer support domain."""

from typing import Literal

from pydantic import BaseModel, Field


class CustomerComplaint(BaseModel):
    category: str = Field(
        ..., description="Complaint category (e.g. shipping, quality)"
    )
    count: int = Field(..., description="Number of complaints in this category")
    sample_texts: list[str] = Field(
        default_factory=list,
        description="Sample complaint texts for context",
    )
    sentiment_score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Average sentiment score (-1 very negative, +1 very positive)",
    )


class CustomerSupportAnalysis(BaseModel):
    kind: Literal["customer_support"]
    period_tickets: int = Field(..., description="Total support tickets in the period")
    previous_period_tickets: int = Field(
        ..., description="Support tickets in the comparison period"
    )
    tickets_change_pct: float | None = Field(
        None, description="Percentage change in tickets vs. comparison period"
    )
    refund_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Refund rate as a fraction of orders"
    )
    return_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Return rate as a fraction of orders"
    )
    negative_reviews: int = Field(
        ..., description="Count of negative reviews (1-2 star) in the period"
    )
    common_issues: list[CustomerComplaint] = Field(
        default_factory=list,
        description="Top complaint categories with details",
    )
    insights: list[str] = Field(
        default_factory=list,
        description="Human-readable insights from the customer support analysis",
    )
