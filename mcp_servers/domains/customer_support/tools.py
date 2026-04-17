"""Customer support domain MCP tools — business logic only, delegates SQL to repository."""

from collections import defaultdict
from datetime import date, timedelta

from .repository import CustomerSupportRepository
from .schemas import CustomerComplaint, CustomerSupportAnalysis


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


async def get_customer_support_snapshot(date_str: str) -> dict:
    """Return customer support metrics for the given date including ticket volume, refund/return rates, top complaint categories, and change vs prior day.

    Args:
        date_str: Target date in YYYY-MM-DD format.
    """
    target = _parse_date(date_str)
    prior = target - timedelta(days=1)

    repo = CustomerSupportRepository()
    target_rows = await repo.fetch_tickets_by_date(target)
    prior_rows = await repo.fetch_tickets_by_date(prior)

    period_tickets = len(target_rows)
    previous_period_tickets = len(prior_rows)

    tickets_change_pct: float | None = None
    if previous_period_tickets > 0:
        tickets_change_pct = round(
            (period_tickets - previous_period_tickets) / previous_period_tickets * 100,
            1,
        )

    refund_count = sum(1 for r in target_rows if r["is_refund"])
    return_count = sum(1 for r in target_rows if r["is_return"])
    refund_rate = refund_count / period_tickets if period_tickets else 0.0
    return_rate = return_count / period_tickets if period_tickets else 0.0

    cat_counts: dict[str, int] = defaultdict(int)
    cat_sentiments: dict[str, list[float]] = defaultdict(list)
    for row in target_rows:
        cat_counts[row["category"]] += 1
        cat_sentiments[row["category"]].append(row["sentiment_score"])

    common_issues = sorted(
        [
            CustomerComplaint(
                category=cat,
                count=count,
                sample_texts=[],
                sentiment_score=round(
                    sum(cat_sentiments[cat]) / len(cat_sentiments[cat]), 2
                ),
            )
            for cat, count in cat_counts.items()
        ],
        key=lambda c: c.count,
        reverse=True,
    )

    negative_reviews = sum(1 for r in target_rows if r["sentiment_score"] < -0.5)

    insights: list[str] = []
    if tickets_change_pct is not None:
        if tickets_change_pct > 50:
            insights.append(
                f"Ticket volume up {tickets_change_pct:+.1f}% vs prior day — strong signal of operational disruption."
            )
        elif tickets_change_pct > 20:
            insights.append(
                f"Ticket volume up {tickets_change_pct:+.1f}% vs prior day."
            )
        elif tickets_change_pct < -20:
            insights.append(
                f"Ticket volume down {tickets_change_pct:+.1f}% vs prior day."
            )
        else:
            insights.append("Support volume within normal range.")
    if refund_rate > 0.1:
        insights.append(
            f"Refund rate elevated at {refund_rate * 100:.1f}% ({refund_count} tickets)."
        )
    if common_issues:
        insights.append(
            f"Top complaint category: {common_issues[0].category} ({common_issues[0].count} tickets)."
        )

    result = CustomerSupportAnalysis(
        kind="customer_support",
        period_tickets=period_tickets,
        previous_period_tickets=previous_period_tickets,
        tickets_change_pct=tickets_change_pct,
        refund_rate=round(refund_rate, 4),
        return_rate=round(return_rate, 4),
        negative_reviews=negative_reviews,
        common_issues=common_issues,
        insights=insights,
    )
    return result.model_dump(mode="json")
