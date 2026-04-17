"""Pydantic models for the sales domain."""

from typing import Literal

from pydantic import BaseModel, Field

from domains.common import Anomaly, ProductRef, Severity, TimeRange


class ProductRevenue(BaseModel):
    product: ProductRef = Field(..., description="Product reference")
    revenue: float = Field(..., description="Revenue attributed to this product")


class SalesMetrics(BaseModel):
    total_revenue: float = Field(..., description="Total revenue in the period")
    order_count: int = Field(..., description="Number of orders placed")
    avg_order_value: float = Field(..., description="Average order value")
    top_products: list[ProductRevenue] = Field(
        default_factory=list,
        description="Top products by revenue",
    )
    by_region: dict[str, float] = Field(
        default_factory=dict,
        description="Revenue breakdown by region",
    )


class SalesAnalysis(BaseModel):
    kind: Literal["sales"]
    period: TimeRange = Field(..., description="Analysis time period")
    metrics: SalesMetrics = Field(..., description="Sales metrics for the period")
    anomalies: list[Anomaly] = Field(
        default_factory=list,
        description="Detected anomalies in sales data",
    )
    insights: list[str] = Field(
        default_factory=list,
        description="Human-readable insights from the sales analysis",
    )
    comparison_period: SalesMetrics | None = Field(
        None, description="Metrics from the comparison period (e.g., last week)"
    )
