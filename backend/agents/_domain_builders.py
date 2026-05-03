"""Pure Python builders that convert raw tool results into DomainFinding objects.

Each builder accepts the ``results`` dict produced by an Agent.run() call
(keyed by tool name, values are typed Pydantic objects) and returns a
DomainFinding, or None if the primary tool was not called.

Keeping this logic here — rather than inline in the node functions — means:
- Each node function is ~8 lines (call agent → unpack → build → return)
- Severity thresholds, merge logic, and summary templates are testable in
  isolation without spinning up the full graph.
- No LLM calls are needed for finding construction; this is deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime

from domains.common import TimeRange
from domains.sales.schemas import SalesAnalysis, SalesMetrics

from core.constants import (
    REFUND_RATE_THRESHOLD,
    REORDER_POINT,
    TICKET_CHANGE_THRESHOLD,
)
from core.enums import AgentDomain, Severity
from schemas.analysis import DomainFinding


def build_sales_finding(results: dict) -> DomainFinding | None:
    """Build a sales DomainFinding from agent tool results.

    Merges comparison and anomaly data into the primary SalesAnalysis object,
    then derives severity from anomaly magnitudes.
    """
    data = _extract_sales(results)
    discount_result = results.get("get_active_discounts")

    if data is None and discount_result is None:
        return None

    if data is None:
        data = _build_sales_fallback(results)

    data = _merge_sales_discounts(data, results)
    data = _merge_sales_comparison(data, results)
    data = _attach_sales_anomalies(data, results)

    return DomainFinding(
        domain=AgentDomain.SALES,
        severity=_sales_severity(data),
        data=data,
    )


def build_inventory_finding(results: dict) -> DomainFinding | None:
    """Build an inventory DomainFinding from agent tool results.

    Merges stockout impact data into the snapshot when available.
    """
    data = _extract_inventory(results)
    if data is None:
        return None

    data = _merge_inventory_impact(data, results)

    return DomainFinding(
        domain=AgentDomain.INVENTORY,
        severity=_inventory_severity(data),
        data=data,
    )


def build_marketing_finding(results: dict) -> DomainFinding | None:
    """Build a marketing DomainFinding from agent tool results."""
    data = _extract_marketing(results)

    if data is None:
        return None

    return DomainFinding(
        domain=AgentDomain.MARKETING,
        severity=_marketing_severity(data),
        data=data,
    )


def build_cx_finding(results: dict) -> DomainFinding | None:
    """Build a customer support DomainFinding from agent tool results.

    Handles three cases:
    - get_customer_support_snapshot only: normal metrics path
    - get_tickets only: build a minimal container with ticket records in insights
    - both: merge ticket records into the snapshot analysis
    """

    cx = _extract_cx(results)
    tickets = _extract_ticket_list(results)

    if cx is None and not tickets:
        return None

    if cx is None:
        return _build_cx_from_tickets(tickets)

    cx = _merge_cx_tickets(cx, tickets)

    return DomainFinding(
        domain=AgentDomain.CUSTOMER_SUPPORT,
        severity=_cx_severity(cx),
        data=cx,
    )


def _extract_inventory(results):
    return results.get("get_inventory_snapshot")


def _extract_sales(results):
    return results.get("get_daily_sales_metrics") or results.get("compare_sales_periods")


def _extract_marketing(results):
    return results.get("get_campaign_status")


def _extract_cx(results):
    return results.get("get_customer_support_snapshot")


def _extract_ticket_list(results):
    tickets = results.get("get_tickets")
    if isinstance(tickets, dict):
        return tickets.get("tickets", [])
    return []


def _inventory_severity(data):
    out_of_stock = [sl for sl in data.stock_levels if sl.is_out_of_stock]
    low_stock = [sl for sl in data.stock_levels if not sl.is_out_of_stock and sl.quantity < REORDER_POINT]

    if out_of_stock:
        return Severity.HIGH
    if low_stock:
        return Severity.MEDIUM
    return Severity.LOW


def _sales_severity(data):
    anomalies = getattr(data, "anomalies", [])
    if not anomalies:
        return Severity.LOW

    sev_order = list(Severity)
    return max((a.severity for a in anomalies), key=lambda s: sev_order.index(s))


def _attach_sales_anomalies(data, results):
    anomalies = results.get("detect_revenue_anomalies") or []
    if isinstance(anomalies, list):
        data.anomalies = anomalies
    return data


def _merge_sales_discounts(data, results):
    discount = results.get("get_active_discounts")
    if discount and isinstance(discount, dict):
        data.active_discounts = discount.get("products_with_active_discounts")
        count = discount.get("total_count", len(data.active_discounts or []))
        data.insights.insert(0, f"{count} product(s) currently have an active discount.")
    return data


def _build_sales_fallback(results):
    from domains.sales.schemas import SalesAnalysis, SalesMetrics

    now = datetime.now(UTC)
    return SalesAnalysis(
        kind="sales",
        period=TimeRange(start=now, end=now),
        metrics=SalesMetrics(total_revenue=0, order_count=0, avg_order_value=0),
    )


def _merge_sales_comparison(data, results):
    comparison = results.get("compare_sales_periods")
    if comparison and comparison.comparison_period:
        data.comparison_period = comparison.comparison_period
        if comparison.insights:
            data.insights = list(dict.fromkeys(comparison.insights + data.insights))
    return data


def _merge_inventory_impact(data, results):
    impact = results.get("get_stockout_impact")
    if impact:
        data.stockout_missed_views = impact.stockout_missed_views
        data.estimated_sales_impact = impact.estimated_sales_impact
        data.insights = list(dict.fromkeys(data.insights + impact.insights))
    return data


def _marketing_severity(data):
    if len(data.underperforming) >= 2:
        return Severity.HIGH
    if data.underperforming:
        return Severity.MEDIUM
    return Severity.LOW


def _cx_severity(cx):
    ticket_change = cx.tickets_change_pct or 0.0

    if ticket_change > TICKET_CHANGE_THRESHOLD or cx.refund_rate > REFUND_RATE_THRESHOLD:
        return Severity.HIGH
    if ticket_change > 20:
        return Severity.MEDIUM
    return Severity.LOW


def _merge_cx_tickets(cx, ticket_list):
    if ticket_list:
        cx.insights.append(f"Retrieved {len(ticket_list)} specific ticket record(s).")
        for t in ticket_list[:5]:
            review = (t.get("review_text") or "")[:80]
            cx.insights.append(f"  [{t['date']}] {t['id']} | {t['category']} | {review}")
    return cx


def _build_cx_from_tickets(ticket_list):
    from domains.customer_support.schemas import CustomerSupportAnalysis

    cx = CustomerSupportAnalysis(
        kind="customer_support",
        period_tickets=len(ticket_list),
        previous_period_tickets=0,
        tickets_change_pct=None,
        refund_rate=0.0,
        return_rate=0.0,
        negative_reviews=0,
        common_issues=[],
        insights=_tickets_to_insights(ticket_list),
    )

    return DomainFinding(
        domain=AgentDomain.CUSTOMER_SUPPORT,
        severity=Severity.LOW,
        data=cx,
    )


def _tickets_to_insights(ticket_list, limit=10):
    insights = [f"Retrieved {len(ticket_list)} ticket record(s)."]

    for t in ticket_list[:limit]:
        flags = []
        if t.get("is_refund"):
            flags.append("refund")
        if t.get("is_return"):
            flags.append("return")

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        review = (t.get("review_text") or "")[:100]

        insights.append(f"[{t['date']}] {t['id']} | {t['category']}{flag_str} | {review}")

    return insights
