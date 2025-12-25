"""Pydantic models for the inventory domain."""

from typing import Literal

from pydantic import BaseModel, Field

from domains.common import ProductRef


class StockLevel(BaseModel):
    product: ProductRef = Field(..., description="Product reference")
    quantity: int = Field(..., description="Current stock quantity")
    unit_price: float | None = Field(
        None, description="Current unit price for this product"
    )
    reorder_point: int | None = Field(
        None, description="Quantity at which reorder is triggered"
    )
    days_until_stockout: float | None = Field(
        None,
        description="Estimated days until stockout based on current sales velocity",
    )
    is_out_of_stock: bool = Field(
        ..., description="Whether the product is currently out of stock"
    )


class InventoryAnalysis(BaseModel):
    kind: Literal["inventory"]
    stock_levels: list[StockLevel] = Field(
        default_factory=list,
        description="Stock levels for all tracked products",
    )
    stockout_missed_views: list[ProductRef] = Field(
        default_factory=list,
        description="Products viewed but not purchased due to stock unavailability",
    )
    estimated_sales_impact: float | None = Field(
        None,
        description="Estimated revenue lost due to stockouts",
    )
    insights: list[str] = Field(
        default_factory=list,
        description="Human-readable insights from the inventory analysis",
    )
