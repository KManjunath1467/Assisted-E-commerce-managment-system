"""Customer support domain MCP tools — business logic only, delegates SQL to repository."""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from db import get_session_factory
from domains.common import parse_date
from domains.db_tables import tickets as _tickets
from sqlalchemy import insert

from .repository import CustomerSupportRepository
from .schemas import CustomerComplaint, CustomerSupportAnalysis


async def get_customer_support_snapshot(date_str: str) -> dict:
    """Return customer support metrics for the given date including ticket volume, refund/return rates, top complaint categories, and change vs prior day.

    Args:
        date_str: Target date in YYYY-MM-DD format.
    """
    target = parse_date(date_str)
    prior = target - timedelta(days=1)

    factory = get_session_factory()
    async with factory() as session:
        repo = CustomerSupportRepository(session)
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


async def get_tickets(
    ticket_id: str = "",
    limit: int = 10,
    category: str = "",
    date_from: str = "",
    date_to: str = "",
) -> dict:
    """Look up individual tickets by ID or list recent tickets with optional filters.

    Use this when the user asks about a specific ticket, wants to see recent tickets,
    or needs to filter tickets by category or date range.

    Note: tickets have no resolution status — they are immutable complaint/support records.
    Available fields per ticket: id, date, category, sentiment_score, is_refund,
    is_return, review_text.

    Args:
        ticket_id: UUID of a specific ticket to look up. Returns that ticket or null if not found.
        limit: Max number of tickets to return for list queries (default 10, max 50).
        category: Filter by category (e.g. "shipping", "quality", "escalation").
        date_from: Start date filter in YYYY-MM-DD format (inclusive).
        date_to: End date filter in YYYY-MM-DD format (inclusive).
    """
    import uuid as _uuid

    factory = get_session_factory()
    async with factory() as session:
        repo = CustomerSupportRepository(session)

        if ticket_id:
            try:
                uid = _uuid.UUID(ticket_id)
            except ValueError:
                return {"error": f"Invalid ticket_id format: {ticket_id!r}"}
            row = await repo.fetch_ticket_by_id(uid)
            if row is None:
                return {"ticket": None, "found": False}
            return {
                "ticket": {
                    "id": str(row["id"]),
                    "date": row["date"].isoformat(),
                    "category": row["category"],
                    "sentiment_score": row["sentiment_score"],
                    "is_refund": row["is_refund"],
                    "is_return": row["is_return"],
                    "review_text": row["review_text"],
                },
                "found": True,
            }

        parsed_from = parse_date(date_from) if date_from else None
        parsed_to = parse_date(date_to) if date_to else None
        capped_limit = min(limit, 50)
        rows = await repo.fetch_recent_tickets(
            limit=capped_limit,
            category=category,
            date_from=parsed_from,
            date_to=parsed_to,
        )

    tickets_out = [
        {
            "id": str(r["id"]),
            "date": r["date"].isoformat(),
            "category": r["category"],
            "sentiment_score": r["sentiment_score"],
            "is_refund": r["is_refund"],
            "is_return": r["is_return"],
            "review_text": r["review_text"],
        }
        for r in rows
    ]
    return {"tickets": tickets_out, "count": len(tickets_out)}


async def create_support_ticket(summary: str, reason: str) -> dict:
    """Request creating an escalation support ticket for human approval. Does NOT create the ticket.

    Args:
        summary: Description of the issue to escalate.
        reason: Brief explanation of why escalation is needed.
    """
    if not summary or not summary.strip():
        raise ValueError("summary must be a non-empty string.")
    return {
        "action_type": "create_support_ticket",
        "targets": ["support-queue"],
        "parameters": {"description": summary},
        "description": f"Create support ticket: {summary[:80]}",
        "reason": reason,
    }


async def execute_create_support_ticket(description: str) -> dict:
    """Insert an escalation support ticket with the given description."""
    ticket_id = uuid.uuid4()
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            insert(_tickets).values(
                id=ticket_id,
                date=datetime.now(UTC).date(),
                category="escalation",
                sentiment_score=-0.5,
                is_refund=False,
                is_return=False,
                review_text=description,
            )
        )
        await session.commit()
    return {"ticket_id": str(ticket_id), "message": "Support ticket created."}
