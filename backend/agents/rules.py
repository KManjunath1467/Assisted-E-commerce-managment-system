"""Deterministic business-rule engine: domain findings → recommended actions.

Kept separate from nodes.py so node wiring and business logic are not mixed
in the same file.
"""

from __future__ import annotations

from core.constants import (
    DISCOUNT_PCT,
    REFUND_RATE_THRESHOLD,
    REORDER_POINT,
    REVENUE_DEVIATION_THRESHOLD,
    ROAS_THRESHOLD,
    TICKET_CHANGE_THRESHOLD,
)
from core.enums import ActionType, AgentDomain, CampaignStatus
from schemas.actions import RecommendedAction
from schemas.analysis import DomainFinding


def build_recommendations(
    findings: list[DomainFinding],
    action_requested: bool = False,
    query: str = "",
) -> list[RecommendedAction]:
    """Derive recommended actions from domain findings using hard-coded business rules.

    When ``action_requested=True`` (user explicitly asked for an action) the
    inventory rule is more permissive: a RESTOCK recommendation is generated
    for products matching the query even if above the automatic threshold.
    If no product in the query can be matched by name, all low/out-of-stock
    products are recommended as a safe fallback.
    """
    recommendations: list[RecommendedAction] = []
    # Normalised query tokens used to match specific product names.
    _query_tokens = {w.lower() for w in query.split() if len(w) > 2}

    for finding in findings:
        if finding.domain == AgentDomain.INVENTORY:
            stock_levels = finding.data.stock_levels

            # When the user requested an action, narrow to products that are
            # name-matched by the query. Only fall back to all stock levels
            # if no match is found (handles generic "restock everything").
            if action_requested and _query_tokens:
                matched = [sl for sl in stock_levels if _query_tokens & {w.lower() for w in sl.product.name.split()}]
                if matched:
                    stock_levels = matched

            for sl in stock_levels:
                if sl.is_out_of_stock:
                    recommendations.append(
                        RecommendedAction(
                            action_type=ActionType.RESTOCK,
                            description=f"Emergency restock of {sl.product.name} ({sl.product.product_id})",
                            rationale="Product is out of stock, causing active revenue loss",
                            requires_approval=True,
                            targets=[sl.product.product_id],
                        )
                    )
                elif sl.quantity <= REORDER_POINT:
                    recommendations.append(
                        RecommendedAction(
                            action_type=ActionType.RESTOCK,
                            description=(
                                f"Restock {sl.product.name} ({sl.product.product_id})"
                                f" — only {sl.quantity} units remaining"
                            ),
                            rationale=(
                                f"Stock level ({sl.quantity}) is at or below the reorder point ({REORDER_POINT})"
                            ),
                            requires_approval=True,
                            targets=[sl.product.product_id],
                        )
                    )
                elif action_requested:
                    # Product was explicitly named in the query but is above
                    # the automatic threshold — still surface it for approval.
                    recommendations.append(
                        RecommendedAction(
                            action_type=ActionType.RESTOCK,
                            description=(
                                f"Restock {sl.product.name} ({sl.product.product_id})"
                                f" — currently {sl.quantity} units in stock"
                            ),
                            rationale="Restock requested by operator; current stock is above the automatic threshold",
                            requires_approval=True,
                            targets=[sl.product.product_id],
                        )
                    )

        if finding.domain == AgentDomain.MARKETING and finding.data.underperforming:
            for camp in finding.data.underperforming:
                if camp.status == CampaignStatus.PAUSED:
                    recommendations.append(
                        RecommendedAction(
                            action_type=ActionType.RESUME_CAMPAIGN,
                            description=f"Resume paused campaign '{camp.name}' with revised budget",
                            rationale="Campaign is paused, reducing top-of-funnel traffic",
                            requires_approval=True,
                            targets=[camp.campaign_id],
                        )
                    )
                else:
                    recommendations.append(
                        RecommendedAction(
                            action_type=ActionType.PAUSE_CAMPAIGN,
                            description=(
                                f"Pause underperforming campaign '{camp.name}' (ROAS {camp.current_period.roas:.2f})"
                            ),
                            rationale=(f"ROAS {camp.current_period.roas:.2f} is below the {ROAS_THRESHOLD} threshold"),
                            requires_approval=True,
                            targets=[camp.campaign_id],
                        )
                    )

        if finding.domain == AgentDomain.SALES and finding.data.anomalies:
            worst = max(finding.data.anomalies, key=lambda a: abs(a.deviation_pct), default=None)
            if worst and worst.deviation_pct < REVENUE_DEVIATION_THRESHOLD:
                # Use top products as human-readable targets; fall back to the
                # metric name only if there are no product-level sales records.
                top_prods = finding.data.metrics.top_products[:3]
                if top_prods:
                    target_ids = [p.product.product_id for p in top_prods]
                    target_label = ", ".join(f"{p.product.name} ({p.product.product_id})" for p in top_prods)
                    description = (
                        f"Run {DISCOUNT_PCT}% discount on top products ({target_label}) "
                        f"to stimulate sales (revenue down {worst.deviation_pct:+.1f}%)"
                    )
                else:
                    target_ids = [worst.metric]
                    description = (
                        f"Run {DISCOUNT_PCT}% discount to stimulate sales (revenue down {worst.deviation_pct:+.1f}%)"
                    )
                recommendations.append(
                    RecommendedAction(
                        action_type=ActionType.RUN_DISCOUNT,
                        description=description,
                        rationale=f"Revenue deviation of {worst.deviation_pct:.1f}% warrants demand stimulation",
                        requires_approval=True,
                        targets=target_ids,
                        parameters={"discount_pct": DISCOUNT_PCT},
                    )
                )

        if finding.domain == AgentDomain.CUSTOMER_SUPPORT:
            ticket_change = finding.data.tickets_change_pct or 0.0
            if ticket_change > TICKET_CHANGE_THRESHOLD or finding.data.refund_rate > REFUND_RATE_THRESHOLD:
                top_issue = finding.data.common_issues[0].category if finding.data.common_issues else "general"
                recommendations.append(
                    RecommendedAction(
                        action_type=ActionType.CREATE_SUPPORT_TICKET,
                        description=(
                            f"Escalate support ticket for '{top_issue}' spike ({ticket_change:+.1f}% ticket increase)"
                        ),
                        rationale=(
                            f"Ticket volume up {ticket_change:+.1f}%, refund rate {finding.data.refund_rate * 100:.1f}%"
                        ),
                        requires_approval=False,
                        targets=["support-queue"],
                    )
                )

    return recommendations
