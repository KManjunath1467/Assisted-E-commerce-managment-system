"""Marketing domain MCP tools — business logic only, delegates SQL to repository."""

import uuid as _uuid
from datetime import UTC, datetime

from db import get_session_factory
from domains.common import parse_date
from domains.db_tables import campaigns as _campaigns
from sqlalchemy import update

from .repository import MarketingRepository
from .schemas import (
    Campaign,
    CampaignMetrics,
    CampaignStatus,
    Channel,
    MarketingAnalysis,
)

ROAS_THRESHOLD = 1.5


async def get_campaign_status(start_date: str = "") -> dict:
    """Get all marketing campaigns, flag underperformers (ROAS < 1.5), and identify the worst channel.

    Args:
        start_date: Optional ISO date (YYYY-MM-DD) for the campaign analysis period. Defaults to today when empty.
    """
    analysis_date = parse_date(start_date) if start_date else datetime.now(UTC).date()
    factory = get_session_factory()
    async with factory() as session:
        repo = MarketingRepository(session)
        rows = await repo.fetch_campaigns()

    campaigns = []
    underperforming = []
    channel_roas: dict[str, list[float]] = {}

    for row in rows:
        perf = row["performance"] or {}
        metrics = CampaignMetrics(
            spend=float(perf.get("spend", 0)),
            impressions=int(perf.get("impressions", 0)),
            clicks=int(perf.get("clicks", 0)),
            conversions=int(perf.get("conversions", 0)),
            roas=float(perf.get("roas", 0.0)),
        )
        try:
            channel = Channel(row["channel"])
        except ValueError:
            channel = Channel.DISPLAY

        try:
            status = CampaignStatus(row["status"].lower())
        except (ValueError, AttributeError):
            status = CampaignStatus.ACTIVE

        campaign = Campaign(
            campaign_id=str(row["id"]),
            name=row["name"],
            channel=channel,
            status=status,
            current_period=metrics,
            start_date=analysis_date,
        )
        campaigns.append(campaign)
        channel_roas.setdefault(row["channel"], []).append(metrics.roas)

        if metrics.roas < ROAS_THRESHOLD:
            underperforming.append(campaign)

    worst_channel = None
    if channel_roas:
        worst = min(
            channel_roas, key=lambda ch: sum(channel_roas[ch]) / len(channel_roas[ch])
        )
        try:
            worst_channel = Channel(worst)
        except ValueError:
            pass

    insights = []
    if underperforming:
        names = ", ".join(c.name for c in underperforming)
        insights.append(f"Underperforming campaigns (ROAS < {ROAS_THRESHOLD}): {names}")
    if worst_channel:
        avg = sum(channel_roas[worst_channel.value]) / len(
            channel_roas[worst_channel.value]
        )
        insights.append(f"Worst channel: {worst_channel.value} (avg ROAS {avg:.2f})")

    result = MarketingAnalysis(
        kind="marketing",
        campaigns=campaigns,
        underperforming=underperforming,
        worst_channel=worst_channel,
        insights=insights,
    )
    return result.model_dump(mode="json")


async def pause_campaign(targets: list[str], reason: str) -> dict:
    """Request pausing campaigns for human approval. Does NOT execute the pause.

    Args:
        targets: List of campaign ID strings to pause.
        reason: Brief explanation of why the campaigns should be paused.
    """
    if not targets:
        raise ValueError("targets must be a non-empty list of campaign IDs.")
    from domains.common import resolve_campaign_labels

    labels = await resolve_campaign_labels(targets)
    return {
        "action_type": "pause_campaign",
        "targets": targets,
        "parameters": {},
        "description": f"Pause campaign(s): {labels}",
        "reason": reason,
    }


async def resume_campaign(targets: list[str], reason: str) -> dict:
    """Request resuming campaigns for human approval. Does NOT execute the resume.

    Args:
        targets: List of campaign ID strings to resume.
        reason: Brief explanation of why the campaigns should be resumed.
    """
    if not targets:
        raise ValueError("targets must be a non-empty list of campaign IDs.")
    from domains.common import resolve_campaign_labels

    labels = await resolve_campaign_labels(targets)
    return {
        "action_type": "resume_campaign",
        "targets": targets,
        "parameters": {},
        "description": f"Resume campaign(s): {labels}",
        "reason": reason,
    }


async def execute_pause_campaign(targets: list[str]) -> dict:
    """Set status='paused' for the given campaign UUIDs."""
    if not targets:
        return {"updated": 0, "message": "No targets specified."}
    factory = get_session_factory()
    async with factory() as session:
        updated = 0
        for campaign_id in targets:
            result = await session.execute(
                update(_campaigns)
                .where(_campaigns.c.id == _uuid.UUID(campaign_id))
                .values(status="paused")
            )
            if result.rowcount:
                updated += result.rowcount
        await session.commit()
    return {"updated": updated, "message": f"Paused {updated} campaign(s)."}


async def execute_resume_campaign(targets: list[str]) -> dict:
    """Set status='active' for the given campaign UUIDs."""
    if not targets:
        return {"updated": 0, "message": "No targets specified."}
    factory = get_session_factory()
    async with factory() as session:
        updated = 0
        for campaign_id in targets:
            result = await session.execute(
                update(_campaigns)
                .where(_campaigns.c.id == _uuid.UUID(campaign_id))
                .values(status="active")
            )
            if result.rowcount:
                updated += result.rowcount
        await session.commit()
    return {"updated": updated, "message": f"Resumed {updated} campaign(s)."}
