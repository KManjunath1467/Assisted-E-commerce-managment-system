"""PostgreSQL incident persistence for the memory layer."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from core.constants import DISCOUNT_PCT
from core.enums import ActionStatus, ActionType, CampaignStatus, IncidentStatus
from db.models import Action, CampaignModel, Incident, Inventory, Thread, ThreadMessage, Ticket
from db.qdrant_store import index_incident
from db.session import get_session_factory

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agents.state import GraphState
    from schemas.actions import RecommendedAction

# How many units to add when a restock is approved.
_RESTOCK_QTY = 200


async def save_incident(state: GraphState) -> str | None:
    """Persist the incident from graph state into the incidents table. Returns incident_id."""
    root_cause = state.get("root_cause")
    query = state.get("query", "")

    # Build a meaningful summary even when root_cause is absent (targeted
    # queries may produce recommendations without a deep root-cause object).
    if root_cause:
        summary = (
            "; ".join(root_cause.primary_cause)
            if isinstance(root_cause.primary_cause, list)
            else root_cause.primary_cause
        )
    else:
        actions = state.get("recommended_actions", []) or []
        summary = "; ".join(a.description for a in actions) or query

    if not summary:
        return None

    signals = {
        "query": query,
        "root_cause": root_cause.model_dump(mode="json") if root_cause else None,
        "domain_findings": [f.model_dump(mode="json") for f in state.get("domain_findings", [])],
    }

    factory = get_session_factory()
    async with factory() as session:
        incident = Incident(
            id=uuid.uuid4(),
            summary=summary,
            signals=signals,
            status=IncidentStatus.OPEN,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(incident)
        await session.commit()
        return str(incident.id)


async def persist_hitl_incident_and_actions(
    state: GraphState,
    recommendations: list[RecommendedAction],
) -> tuple[str, list[dict]]:
    """Create an incident + action DB rows for HITL approval.

    Reuses an existing incident_id from state if already set.
    Returns (incident_id, list of action dicts ready for the interrupt payload).
    """
    root_cause = state.get("root_cause")
    if root_cause:
        summary = (
            "; ".join(root_cause.primary_cause)
            if isinstance(root_cause.primary_cause, list)
            else root_cause.primary_cause
        )
        signals = {
            "query": state.get("query", ""),
            "root_cause": root_cause.model_dump(mode="json"),
            "domain_findings": [f.model_dump(mode="json") for f in state.get("domain_findings", [])],
        }
    else:
        summary = state.get("query", "")
        signals = {"query": state.get("query", "")}

    incident_id = state.get("incident_id")
    thread_id = state.get("thread_id")
    factory = get_session_factory()
    action_rows: list[dict] = []

    async with factory() as session:
        if not incident_id:
            now = datetime.now(UTC)
            incident = Incident(
                id=uuid.uuid4(),
                summary=summary,
                signals=signals,
                status=IncidentStatus.OPEN,
                created_at=now,
                updated_at=now,
            )
            session.add(incident)
            await session.flush()
            incident_id = str(incident.id)

        for rec in recommendations:
            now = datetime.now(UTC)
            action = Action(
                id=uuid.uuid4(),
                incident_id=uuid.UUID(incident_id),
                thread_id=thread_id,
                action_type=rec.action_type,
                description=rec.description,
                parameters={"targets": rec.targets, **rec.parameters},
                status=ActionStatus.PENDING_APPROVAL,
                created_at=now,
                updated_at=now,
            )
            session.add(action)
            action_rows.append(
                {
                    "id": str(action.id),
                    "incident_id": incident_id,
                    "action_type": rec.action_type.value,
                    "description": rec.description,
                    "status": ActionStatus.PENDING_APPROVAL.value,
                    "created_at": now.isoformat(),
                }
            )

        await session.commit()

    return incident_id, action_rows


# ─── Actions ──────────────────────────────────────────────────────────────────


async def get_actions_by_thread(thread_id: str, *, pending_only: bool = False) -> list[dict]:
    """Return actions linked to a given thread.

    Args:
        thread_id: The thread to query.
        pending_only: When True, only return actions still in PENDING_APPROVAL status.
    """
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(Action).where(Action.thread_id == thread_id).order_by(Action.created_at)
        if pending_only:
            stmt = stmt.where(Action.status == ActionStatus.PENDING_APPROVAL)
        rows = (await session.execute(stmt)).scalars().all()
    return [_action_to_dict(r) for r in rows]


async def cancel_pending_actions_for_thread(thread_id: str) -> int:
    """Bulk-reject all PENDING_APPROVAL actions for a thread.

    Used when clearing a stale interrupt so orphaned actions don't pollute
    subsequent HITL rounds on the same thread.  Returns the count of cancelled actions.
    """
    factory = get_session_factory()
    now = datetime.now(UTC)
    cancelled = 0
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(Action).where(
                        Action.thread_id == thread_id,
                        Action.status == ActionStatus.PENDING_APPROVAL,
                    )
                )
            )
            .scalars()
            .all()
        )
        for action in rows:
            action.status = ActionStatus.REJECTED
            action.updated_at = now
            cancelled += 1
        await session.commit()
    return cancelled


async def get_action_by_id(action_id: uuid.UUID) -> dict | None:
    """Return a single action row as a dict, or None if not found."""
    factory = get_session_factory()
    async with factory() as session:
        row = (await session.execute(select(Action).where(Action.id == action_id))).scalar_one_or_none()

    if row is None:
        return None
    return _action_to_dict(row)


async def get_pending_actions() -> list[dict]:
    """Return all actions with PENDING_APPROVAL status."""
    factory = get_session_factory()
    async with factory() as session:
        rows = (
            (await session.execute(select(Action).where(Action.status == ActionStatus.PENDING_APPROVAL)))
            .scalars()
            .all()
        )

    return [_action_to_dict(r) for r in rows]


async def get_all_actions() -> list[dict]:
    """Return all actions regardless of status, most recent first."""
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(Action).order_by(Action.created_at.desc()))).scalars().all()

    return [_action_to_dict(r) for r in rows]


async def approve_action_in_db(
    action_id: uuid.UUID, approved: bool, notes: str | None
) -> tuple[Action, ActionStatus, str, datetime | None]:
    """Apply approval/rejection to an Action row and run the business operation.

    Returns (action, final_status, message, executed_at).
    Raises LookupError on not-found, ValueError on wrong status.
    """
    factory = get_session_factory()
    async with factory() as session:
        # FOR UPDATE prevents two concurrent approvals from both reading
        # PENDING_APPROVAL and both executing the business operation.
        action = (
            await session.execute(select(Action).where(Action.id == action_id).with_for_update())
        ).scalar_one_or_none()

        if action is None:
            raise LookupError("Action not found.")
        if action.status != ActionStatus.PENDING_APPROVAL:
            raise ValueError(f"Action is not pending approval (current status: {action.status}).")

        now = datetime.now(UTC)
        if approved:
            # Run the actual business operation before marking as executed.
            op_msg = await _execute_business_operation(session, action, now)
            action.status = ActionStatus.EXECUTED
            action.executed_at = now
            msg = op_msg or f"Action '{action.description}' approved and executed."
            final_status = ActionStatus.EXECUTED
        else:
            action.status = ActionStatus.REJECTED
            now = None  # type: ignore[assignment]
            msg = f"Action '{action.description}' rejected. Notes: {notes or 'none'}"
            final_status = ActionStatus.REJECTED

        await session.commit()
        return action, final_status, msg, now


async def _execute_business_operation(session, action: Action, now: datetime) -> str | None:
    """Run the domain-side database mutation for an approved action.

    Returns a human-readable result message, or None to use the default.
    The caller owns the session transaction and commits after this returns.
    """
    targets: list[str] = (action.parameters or {}).get("targets", [])
    atype = action.action_type

    if atype == ActionType.RESTOCK:
        if not targets:
            return None
        updated = 0
        for product_id in targets:
            result = await session.execute(select(Inventory).where(Inventory.product_id == product_id))
            inv = result.scalar_one_or_none()
            if inv is not None:
                inv.stock += _RESTOCK_QTY
                inv.updated_at = now
                updated += 1
        return (
            f"Restocked {updated} product(s) by {_RESTOCK_QTY} units each."
            if updated
            else f"No inventory rows found for targets: {targets}"
        )

    if atype == ActionType.PAUSE_CAMPAIGN:
        if not targets:
            return None
        updated = 0
        for campaign_id in targets:
            result = await session.execute(select(CampaignModel).where(CampaignModel.id == uuid.UUID(campaign_id)))
            camp = result.scalar_one_or_none()
            if camp is not None and camp.status != CampaignStatus.PAUSED:
                camp.status = CampaignStatus.PAUSED
                updated += 1
        return f"Paused {updated} campaign(s)." if updated else "Campaigns already paused."

    if atype == ActionType.RESUME_CAMPAIGN:
        if not targets:
            return None
        updated = 0
        for campaign_id in targets:
            result = await session.execute(select(CampaignModel).where(CampaignModel.id == uuid.UUID(campaign_id)))
            camp = result.scalar_one_or_none()
            if camp is not None and camp.status != CampaignStatus.ACTIVE:
                camp.status = CampaignStatus.ACTIVE
                updated += 1
        return f"Resumed {updated} campaign(s)." if updated else "Campaigns already active."

    if atype == ActionType.RUN_DISCOUNT:
        # Targets are product_ids. Set discount_pct and activate the discount
        # flag on each product; unit_price remains the canonical base price.
        if not targets:
            return None
        from db.models import Product

        pct = int((action.parameters or {}).get("discount_pct", DISCOUNT_PCT))
        updated = 0
        for product_id in targets:
            result = await session.execute(select(Product).where(Product.product_id == product_id))
            prod = result.scalar_one_or_none()
            if prod is not None:
                prod.discount_pct = pct
                prod.discount_active = True
                updated += 1
        return (
            f"Discount of {pct}% activated for {updated} product(s). "
            "unit_price unchanged; apply discount_pct at checkout."
            if updated
            else f"No products found for targets: {targets}"
        )

    if atype == ActionType.CREATE_SUPPORT_TICKET:
        ticket = Ticket(
            id=uuid.uuid4(),
            date=now.date(),
            category="escalation",
            sentiment_score=-0.5,
            is_refund=False,
            is_return=False,
            review_text=action.description,
        )
        session.add(ticket)
        return f"Support ticket created for: {action.description}"

    return None


# ─── Incidents ────────────────────────────────────────────────────────────────


def _action_to_dict(row: Action) -> dict:
    return {
        "id": str(row.id),
        "incident_id": str(row.incident_id),
        "action_type": row.action_type.value,
        "description": row.description,
        "status": row.status.value,
        "created_at": row.created_at.isoformat(),
        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
        "thread_id": row.thread_id,
    }


def _incident_to_dict(row: Incident, actions: list[Action]) -> dict:
    signals = row.signals or {}
    return {
        "id": str(row.id),
        "summary": row.summary,
        "status": row.status.value,
        "created_at": row.created_at.isoformat(),
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "signals": signals,
        "resolution_summary": signals.get("resolution_summary"),
        "actions": [_action_to_dict(a) for a in actions],
    }


async def get_all_incidents() -> list[dict]:
    """Return all incidents ordered by most recent, with their actions."""
    from collections import defaultdict

    factory = get_session_factory()
    async with factory() as session:
        incident_rows = (await session.execute(select(Incident).order_by(Incident.created_at.desc()))).scalars().all()

        if not incident_rows:
            return []

        incident_ids = [r.id for r in incident_rows]
        action_rows = (
            (await session.execute(select(Action).where(Action.incident_id.in_(incident_ids)))).scalars().all()
        )

    by_incident: dict[uuid.UUID, list[Action]] = defaultdict(list)
    for a in action_rows:
        by_incident[a.incident_id].append(a)

    return [_incident_to_dict(r, by_incident[r.id]) for r in incident_rows]


async def get_incident_by_id(incident_id: uuid.UUID) -> dict | None:
    """Return a single incident with its actions, or None if not found."""
    factory = get_session_factory()
    async with factory() as session:
        incident = (await session.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()

        if incident is None:
            return None

        actions = (await session.execute(select(Action).where(Action.incident_id == incident_id))).scalars().all()

    return _incident_to_dict(incident, actions)


async def resolve_incident_in_db(
    incident_id: uuid.UUID,
    resolution_summary: str | None = None,
) -> dict:
    """Mark an incident resolved and auto-reject pending actions.

    Optionally stores a *resolution_summary* note in the signals JSONB.
    Raises LookupError if not found, ValueError if already resolved.
    """
    factory = get_session_factory()
    async with factory() as session:
        incident = (await session.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()

        if incident is None:
            raise LookupError("Incident not found.")
        if incident.status == IncidentStatus.RESOLVED:
            raise ValueError("Incident is already resolved.")

        now = datetime.now(UTC)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now
        incident.updated_at = now

        if resolution_summary:
            signals = dict(incident.signals or {})
            signals["resolution_summary"] = resolution_summary
            incident.signals = signals

        pending = (
            (
                await session.execute(
                    select(Action).where(
                        Action.incident_id == incident_id,
                        Action.status == ActionStatus.PENDING_APPROVAL,
                    )
                )
            )
            .scalars()
            .all()
        )

        for action in pending:
            action.status = ActionStatus.REJECTED
            action.updated_at = now

        await session.commit()

        all_actions = (await session.execute(select(Action).where(Action.incident_id == incident_id))).scalars().all()

    # Re-index into Qdrant with the actual executed actions so future similar
    # incidents can discover what resolved this one.
    # Qdrant is treated as eventually consistent — failures are logged but do
    # not roll back the already-committed DB state.
    executed_action_types = [action.action_type for action in all_actions if action.status == ActionStatus.EXECUTED]
    summary_str = incident.summary if isinstance(incident.summary, str) else "; ".join(incident.summary)
    signals = incident.signals or {}
    try:
        await index_incident(
            incident_id=str(incident.id),
            summary=summary_str,
            actions_taken=executed_action_types,
            query=signals.get("query", ""),
        )
    except Exception:
        logger.error("Qdrant index_incident failed for %s; DB commit already succeeded", incident.id, exc_info=True)

    return _incident_to_dict(incident, all_actions)


# ─── Threads ──────────────────────────────────────────────────────────────────


async def ensure_thread(thread_id: str, title: str) -> None:
    """Create or update a thread row. Safe to call multiple times (upsert)."""
    factory = get_session_factory()
    async with factory() as session:
        existing = (await session.execute(select(Thread).where(Thread.thread_id == thread_id))).scalar_one_or_none()
        if existing is None:
            session.add(Thread(thread_id=thread_id, title=title[:100]))
        else:
            existing.updated_at = datetime.now(UTC)
        await session.commit()


async def persist_thread_messages(
    thread_id: str,
    user_content: dict,
    assistant_content: dict,
) -> None:
    """Append a user + assistant message pair to an existing thread."""
    factory = get_session_factory()
    async with factory() as session:
        session.add(ThreadMessage(thread_id=thread_id, role="user", content=user_content))
        session.add(ThreadMessage(thread_id=thread_id, role="assistant", content=assistant_content))
        await session.commit()


async def get_all_threads() -> list[dict]:
    """Return all threads ordered by most recently updated first."""
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(Thread).order_by(Thread.updated_at.desc()))).scalars().all()
    return [
        {
            "thread_id": t.thread_id,
            "title": t.title,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in rows
    ]


async def get_thread_messages(thread_id: str) -> list[dict] | None:
    """Return all messages for a thread ordered by creation time, or None if thread not found."""
    factory = get_session_factory()
    async with factory() as session:
        thread_row = await session.get(Thread, thread_id)
        if thread_row is None:
            return None
        rows = (
            (
                await session.execute(
                    select(ThreadMessage)
                    .where(ThreadMessage.thread_id == thread_id)
                    .order_by(ThreadMessage.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at,
        }
        for m in rows
    ]
