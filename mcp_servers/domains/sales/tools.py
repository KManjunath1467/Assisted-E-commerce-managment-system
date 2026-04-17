"""Sales domain MCP tools — business logic only, delegates SQL to repository."""

from datetime import UTC, date, datetime, timedelta

from .repository import SalesRepository
from .schemas import (
    Anomaly,
    ProductRef,
    ProductRevenue,
    SalesAnalysis,
    SalesMetrics,
    Severity,
    TimeRange,
)


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


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
    repo = SalesRepository()
    start = _parse_date(start_date)
    end = _parse_date(end_date) if end_date else start
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
    repo = SalesRepository()
    target = _parse_date(current_date)
    current_metrics, _ = await _sales_metrics_for_range(repo, target, target)

    prior_start = target - timedelta(days=days_back)
    prior_end = target - timedelta(days=1)
    prior_metrics, _ = await _sales_metrics_for_range(repo, prior_start, prior_end)
    days_count = days_back or 1

    comparison = SalesMetrics(
        total_revenue=prior_metrics.total_revenue / days_count,
        order_count=int(prior_metrics.order_count / days_count),
        avg_order_value=prior_metrics.avg_order_value,
        top_products=[
            ProductRevenue(product=p.product, revenue=p.revenue / days_count)
            for p in prior_metrics.top_products
        ],
        by_region={k: v / days_count for k, v in prior_metrics.by_region.items()},
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
    repo = SalesRepository()
    target = _parse_date(current_date)
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
