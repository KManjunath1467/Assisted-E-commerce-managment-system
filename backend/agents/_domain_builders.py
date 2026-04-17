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
    sales_data = results.get("get_daily_sales_metrics") or results.get("compare_sales_periods")
    if sales_data is None:
        return None

    # Merge comparison period insights into the primary analysis if available.
    comparison = results.get("compare_sales_periods")
    if comparison and comparison.comparison_period:
        sales_data.comparison_period = comparison.comparison_period
        if comparison.insights:
            sales_data.insights = list(dict.fromkeys(comparison.insights + sales_data.insights))

    # Attach anomaly list returned by detect_revenue_anomalies.
    anomalies = results.get("detect_revenue_anomalies") or []
    if isinstance(anomalies, list):
        sales_data.anomalies = anomalies

    # Severity is driven by the worst anomaly detected; LOW if none.
    severity = Severity.LOW
    if anomalies:
        sev_order = list(Severity)
        severity = max((a.severity for a in anomalies), key=lambda s: sev_order.index(s))

    return DomainFinding(
        domain=AgentDomain.SALES,
        severity=severity,
        data=sales_data,
    )


def build_inventory_finding(results: dict) -> DomainFinding | None:
    """Build an inventory DomainFinding from agent tool results.

    Merges stockout impact data into the snapshot when available.
    """
    snapshot = results.get("get_inventory_snapshot")
    if snapshot is None:
        return None

    # Merge stockout impact data when the LLM chose to call get_stockout_impact.
    impact = results.get("get_stockout_impact")
    if impact:
        snapshot.stockout_missed_views = impact.stockout_missed_views
        snapshot.estimated_sales_impact = impact.estimated_sales_impact
        snapshot.insights = list(dict.fromkeys(snapshot.insights + impact.insights))

    out_of_stock = [sl.product for sl in snapshot.stock_levels if sl.is_out_of_stock]
    low_stock = [sl for sl in snapshot.stock_levels if not sl.is_out_of_stock and sl.quantity < REORDER_POINT]

    severity = Severity.HIGH if out_of_stock else Severity.MEDIUM if low_stock else Severity.LOW

    return DomainFinding(
        domain=AgentDomain.INVENTORY,
        severity=severity,
        data=snapshot,
    )


def build_marketing_finding(results: dict) -> DomainFinding | None:
    """Build a marketing DomainFinding from agent tool results."""
    analysis = results.get("get_campaign_status")
    if analysis is None:
        return None

    severity = (
        Severity.HIGH
        if len(analysis.underperforming) >= 2
        else Severity.MEDIUM
        if analysis.underperforming
        else Severity.LOW
    )
    return DomainFinding(
        domain=AgentDomain.MARKETING,
        severity=severity,
        data=analysis,
    )


def build_cx_finding(results: dict) -> DomainFinding | None:
    """Build a customer support DomainFinding from agent tool results."""
    cx = results.get("get_customer_support_snapshot")
    if cx is None:
        return None

    ticket_change = cx.tickets_change_pct or 0.0
    severity = (
        Severity.HIGH
        if ticket_change > TICKET_CHANGE_THRESHOLD or cx.refund_rate > REFUND_RATE_THRESHOLD
        else Severity.MEDIUM
        if ticket_change > 20
        else Severity.LOW
    )

    return DomainFinding(
        domain=AgentDomain.CUSTOMER_SUPPORT,
        severity=severity,
        data=cx,
    )
