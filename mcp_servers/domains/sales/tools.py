"""Sales domain MCP tools — business logic only, delegates SQL to repository."""

from datetime import UTC, date, datetime, timedelta

from db import get_session_factory
from sqlalchemy import update

from domains.common import Anomaly, ProductRef, Severity, TimeRange, parse_date
from domains.db_tables import products as _products

from .repository import SalesRepository
from .schemas import (
    ProductRevenue,
    SalesAnalysis,
    SalesMetrics,
)


def _make_time_range(start_d: date, end_d: date | None = None) -> TimeRange:
    if end_d is None:
        end_d = start_d
    return TimeRange(
        start=datetime(start_d.year, start_d.month, start_d.day, 0, 0, 0, tzinfo=UTC),
        end=datetime(end_d.year, end_d.month, end_d.day, 23, 59, 59, tzinfo=UTC),
    )


async def _sales_metrics_for_range(
    repo: SalesRepository, start: date, end: date
) -> tuple[SalesMetrics, dict[str, str]]:
    rows = await repo.fetch_sales_by_date_range(start, end)
    products = await repo.fetch_products()
    name_map = {p["product_id"]: p["name"] for p in products}

    total_revenue = sum(float(r["revenue"]) for r in rows)
    order_count = len(rows)
    aov = total_revenue / order_count if order_count else 0.0

    prod_rev: dict[str, float] = {}
    by_region: dict[str, float] = {}
    for r in rows:
        prod_rev[r["product_id"]] = prod_rev.get(r["product_id"], 0.0) + float(
            r["revenue"]
        )
        by_region[r["region"]] = by_region.get(r["region"], 0.0) + float(r["revenue"])

    top_products = sorted(
        [
            ProductRevenue(
                product=ProductRef(product_id=pid, name=name_map.get(pid, pid)),
                revenue=rev,
            )
            for pid, rev in prod_rev.items()
        ],
        key=lambda x: x.revenue,
        reverse=True,
    )[:5]

    return (
        SalesMetrics(
            total_revenue=total_revenue,
            order_count=order_count,
            avg_order_value=aov,
            top_products=top_products,
            by_region=by_region,
        ),
        name_map,
    )


def _generate_insights(m: SalesMetrics) -> list[str]:
    insights = []
    if m.total_revenue == 0:
        insights.append("No revenue recorded for this period.")
    elif m.order_count > 0:
        insights.append(
            f"Total revenue ${m.total_revenue:,.2f} across {m.order_count} orders (AOV ${m.avg_order_value:,.2f})"
        )
    if m.top_products:
        top = m.top_products[0]
        insights.append(f"Top product: {top.product.name} (${top.revenue:,.2f})")
    return insights


async def get_daily_sales_metrics(start_date: str, end_date: str = "") -> dict:
    """Get aggregated sales metrics (revenue, orders, AOV, top products, by-region) for a date or date range.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format (inclusive). Omit or leave empty for a single day.
    """
    start = parse_date(start_date)
    end = parse_date(end_date) if end_date else start
    factory = get_session_factory()
    async with factory() as session:
        repo = SalesRepository(session)
        metrics, _ = await _sales_metrics_for_range(repo, start, end)
    result = SalesAnalysis(
        kind="sales",
        period=_make_time_range(start, end),
        metrics=metrics,
        insights=_generate_insights(metrics),
    )
    return result.model_dump(mode="json")


async def compare_sales_periods(current_date: str, days_back: int = 7) -> dict:
    """Compare sales for current_date against the prior days_back-day average.

    Args:
        current_date: The target date in YYYY-MM-DD format.
        days_back: Number of prior days to average for comparison (default 7).
    """
    if days_back < 1:
        raise ValueError("days_back must be >= 1")
    target = parse_date(current_date)
    factory = get_session_factory()
    async with factory() as session:
        repo = SalesRepository(session)
        current_metrics, _ = await _sales_metrics_for_range(repo, target, target)

        prior_start = target - timedelta(days=days_back)
        prior_end = target - timedelta(days=1)
        prior_metrics, _ = await _sales_metrics_for_range(repo, prior_start, prior_end)

    comparison = SalesMetrics(
        total_revenue=prior_metrics.total_revenue / days_back,
        order_count=int(prior_metrics.order_count / days_back),
        avg_order_value=prior_metrics.avg_order_value,
        top_products=[
            ProductRevenue(product=p.product, revenue=p.revenue / days_back)
            for p in prior_metrics.top_products
        ],
        by_region={k: v / days_back for k, v in prior_metrics.by_region.items()},
    )

    insights = _generate_insights(current_metrics)
    if comparison.total_revenue > 0:
        change_pct = (
            (current_metrics.total_revenue - comparison.total_revenue)
            / comparison.total_revenue
            * 100
        )
        insights.insert(0, f"Revenue vs {days_back}-day daily avg: {change_pct:+.1f}%")

    result = SalesAnalysis(
        kind="sales",
        period=_make_time_range(target, target),
        metrics=current_metrics,
        comparison_period=comparison,
        insights=insights,
    )
    return result.model_dump(mode="json")


async def detect_revenue_anomalies(current_date: str) -> list[dict]:
    """Detect revenue anomalies by comparing current_date against a 7-day rolling average. Flags >20% deviation.

    Args:
        current_date: The date to check for anomalies in YYYY-MM-DD format.
    """
    target = parse_date(current_date)
    factory = get_session_factory()
    async with factory() as session:
        repo = SalesRepository(session)
        current_metrics, _ = await _sales_metrics_for_range(repo, target, target)

        prior_start = target - timedelta(days=7)
        prior_end = target - timedelta(days=1)
        prior_rows = await repo.fetch_sales_by_date_range(prior_start, prior_end)

    daily_revs: dict[date, float] = {}
    for r in prior_rows:
        d = r["date"]
        daily_revs.setdefault(d, 0.0)
        daily_revs[d] += float(r["revenue"])

    if not daily_revs:
        return []

    avg_rev = sum(daily_revs.values()) / len(daily_revs)
    anomalies: list[Anomaly] = []
    if avg_rev > 0:
        deviation = (current_metrics.total_revenue - avg_rev) / avg_rev * 100
        if abs(deviation) > 20:
            anomalies.append(
                Anomaly(
                    metric="daily_revenue",
                    expected=avg_rev,
                    actual=current_metrics.total_revenue,
                    deviation_pct=deviation,
                    severity=Severity.HIGH if abs(deviation) > 40 else Severity.MEDIUM,
                )
            )

    daily_order_counts: dict[date, int] = {}
    for r in prior_rows:
        d = r["date"]
        daily_order_counts[d] = daily_order_counts.get(d, 0) + 1
    avg_orders = (
        sum(daily_order_counts.values()) / len(daily_order_counts)
        if daily_order_counts
        else 0
    )
    if avg_orders > 0:
        order_dev = (current_metrics.order_count - avg_orders) / avg_orders * 100
        if abs(order_dev) > 20:
            anomalies.append(
                Anomaly(
                    metric="daily_order_count",
                    expected=avg_orders,
                    actual=float(current_metrics.order_count),
                    deviation_pct=order_dev,
                    severity=Severity.MEDIUM,
                )
            )

    return [a.model_dump(mode="json") for a in anomalies]


async def get_active_discounts() -> dict:
    """Get all products that currently have an active discount applied.

    Returns product_id, name, category, unit_price, and discount_pct for each
    product where discount_active is True.
    """
    factory = get_session_factory()
    async with factory() as session:
        repo = SalesRepository(session)
        products = await repo.fetch_products()
    active = [
        {
            "product_id": p["product_id"],
            "name": p["name"],
            "category": p.get("category"),
            "unit_price": float(p["unit_price"]),
            "discount_pct": p["discount_pct"],
        }
        for p in products
        if p.get("discount_active")
    ]
    return {"products_with_active_discounts": active, "total_count": len(active)}


async def run_discount(targets: list[str], discount_pct: int, reason: str) -> dict:
    """Request a discount action for human approval. Does NOT execute the discount.

    Args:
        targets: List of product_id strings or product names to apply the discount to.
        discount_pct: Discount percentage (1-50).
        reason: Brief explanation of why the discount is recommended.
    """
    if not targets:
        raise ValueError("targets must be a non-empty list of product IDs.")
    if not (0 < discount_pct <= 50):
        raise ValueError("discount_pct must be between 1 and 50.")
    from domains.common import resolve_product_ids, resolve_product_labels

    targets = await resolve_product_ids(targets)
    if not targets:
        raise ValueError("None of the provided targets matched a known product.")
    labels = await resolve_product_labels(targets)
    return {
        "action_type": "run_discount",
        "targets": targets,
        "parameters": {"discount_pct": discount_pct},
        "description": f"Run {discount_pct}% discount on {labels}",
        "reason": reason,
    }


async def execute_run_discount(targets: list[str], discount_pct: int = 15) -> dict:
    """Activate a discount on specified products. Sets discount_pct and discount_active=True."""
    if not targets:
        return {"updated": 0, "message": "No targets specified."}
    from domains.common import resolve_product_ids

    targets = await resolve_product_ids(targets)
    factory = get_session_factory()
    async with factory() as session:
        updated = 0
        for product_id in targets:
            result = await session.execute(
                update(_products)
                .where(_products.c.product_id == product_id)
                .values(discount_pct=discount_pct, discount_active=True)
            )
            if result.rowcount:
                updated += result.rowcount
        await session.commit()
    return {
        "updated": updated,
        "message": f"Discount of {discount_pct}% activated for {updated} product(s).",
    }
