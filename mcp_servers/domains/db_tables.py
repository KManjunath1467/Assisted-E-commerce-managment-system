"""Shared SQLAlchemy table definitions for all MCP domain repositories."""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

products = Table(
    "products",
    metadata,
    Column("product_id", String, key="product_id"),
    Column("name", String, key="name"),
    Column("category", String, key="category"),
    Column("unit_price", Numeric(10, 2), key="unit_price"),
    Column("discount_pct", Numeric(5, 2), key="discount_pct"),
    Column("discount_active", Boolean, key="discount_active"),
)

sales = Table(
    "sales",
    metadata,
    Column("date", Date, key="date"),
    Column("product_id", String, key="product_id"),
    Column("revenue", Numeric(12, 2), key="revenue"),
    Column("quantity", Integer, key="quantity"),
    Column("region", String, key="region"),
)

inventory = Table(
    "inventory",
    metadata,
    Column("product_id", String, key="product_id"),
    Column("stock", Integer, key="stock"),
)

campaigns = Table(
    "campaigns",
    metadata,
    Column("id", UUID(as_uuid=True), key="id"),
    Column("name", String, key="name"),
    Column("channel", String, key="channel"),
    Column("status", String, key="status"),
    Column("performance", JSONB, key="performance"),
)

tickets = Table(
    "tickets",
    metadata,
    Column("id", UUID(as_uuid=True), key="id"),
    Column("date", Date, key="date"),
    Column("category", String, key="category"),
    Column("sentiment_score", Float, key="sentiment_score"),
    Column("is_refund", Boolean, key="is_refund"),
    Column("is_return", Boolean, key="is_return"),
    Column("review_text", Text, key="review_text"),
)
