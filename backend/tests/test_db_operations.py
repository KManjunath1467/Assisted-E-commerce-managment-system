"""Tests for database persistence operations (pg_store).

These tests require a real Postgres database.  Use the ``require_db`` fixture
to skip when the DB is unavailable.
"""

from __future__ import annotations

import uuid

import pytest

from core.enums import ActionStatus, ActionType
from db.pg_store import (
    approve_action_in_db,
    ensure_thread,
    get_action_by_id,
    get_pending_actions,
    persist_hitl_incident_and_actions,
    resolve_incident_in_db,
)

pytestmark = pytest.mark.asyncio


# ── persist_hitl_incident_and_actions ─────────────────────────────────────────


async def test_persist_hitl_saves_thread_id(require_db):
    """Verify that thread_id is propagated to Action rows."""
    from schemas.actions import RecommendedAction

    thread_id = str(uuid.uuid4())
    state = {
        "query": "test query",
        "thread_id": thread_id,
        "root_cause": None,
        "domain_findings": [],
        "incident_id": None,
    }
    recs = [
        RecommendedAction(
            action_type=ActionType.RESTOCK,
            description="Restock test product",
            rationale="Low stock",
            requires_approval=True,
            targets=["PROD-001"],
            parameters={},
        ),
    ]

    await ensure_thread(thread_id, "test")
    incident_id, action_rows = await persist_hitl_incident_and_actions(state, recs)
    assert incident_id is not None
    assert len(action_rows) == 1

    # Fetch the action from DB and verify thread_id.
    action_dict = await get_action_by_id(uuid.UUID(action_rows[0]["id"]))
    assert action_dict is not None
    assert action_dict["thread_id"] == thread_id


async def test_persist_hitl_reuses_incident_id(require_db):
    """When incident_id is already set, reuse it rather than creating a new one."""
    from schemas.actions import RecommendedAction

    # First, create an incident.
    state_1 = {
        "query": "initial query",
        "thread_id": str(uuid.uuid4()),
        "root_cause": None,
        "domain_findings": [],
        "incident_id": None,
    }
    recs = [
        RecommendedAction(
            action_type=ActionType.RESTOCK,
            description="first action",
            rationale="test",
            requires_approval=True,
            targets=[],
            parameters={},
        ),
    ]
    await ensure_thread(state_1["thread_id"], "test")
    incident_id_1, _ = await persist_hitl_incident_and_actions(state_1, recs)

    # Second call reuses existing incident_id.
    state_2 = {**state_1, "incident_id": incident_id_1}
    incident_id_2, action_rows_2 = await persist_hitl_incident_and_actions(state_2, recs)
    assert incident_id_2 == incident_id_1
    assert len(action_rows_2) == 1


# ── resolve_incident_in_db ────────────────────────────────────────────────────


async def test_resolve_auto_rejects_pending_actions(require_db):
    """Resolving an incident should auto-reject its pending actions."""
    from schemas.actions import RecommendedAction

    state = {
        "query": "resolve test",
        "thread_id": str(uuid.uuid4()),
        "root_cause": None,
        "domain_findings": [],
        "incident_id": None,
    }
    recs = [
        RecommendedAction(
            action_type=ActionType.RESTOCK,
            description="will be auto-rejected",
            rationale="test",
            requires_approval=True,
            targets=[],
            parameters={},
        ),
    ]
    await ensure_thread(state["thread_id"], "test")
    incident_id, action_rows = await persist_hitl_incident_and_actions(state, recs)

    result = await resolve_incident_in_db(uuid.UUID(incident_id))
    assert result["status"] == "resolved"
    # The pending action should now be rejected.
    for action in result["actions"]:
        assert action["status"] == "rejected"


async def test_resolve_already_resolved_raises(require_db):
    """Resolving an already-resolved incident should raise ValueError."""
    from schemas.actions import RecommendedAction

    state = {
        "query": "double resolve test",
        "thread_id": str(uuid.uuid4()),
        "root_cause": None,
        "domain_findings": [],
        "incident_id": None,
    }
    await ensure_thread(state["thread_id"], "test")
    incident_id, _ = await persist_hitl_incident_and_actions(
        state,
        [
            RecommendedAction(
                action_type=ActionType.RESTOCK,
                description="x",
                rationale="t",
                requires_approval=True,
                targets=[],
                parameters={},
            )
        ],
    )
    await resolve_incident_in_db(uuid.UUID(incident_id))

    with pytest.raises(ValueError, match="already resolved"):
        await resolve_incident_in_db(uuid.UUID(incident_id))


# ── approve_action_in_db ─────────────────────────────────────────────────────


async def test_approve_action_executes(require_db):
    """Approving a pending action should execute the business operation."""
    from schemas.actions import RecommendedAction

    state = {
        "query": "approve test",
        "thread_id": str(uuid.uuid4()),
        "root_cause": None,
        "domain_findings": [],
        "incident_id": None,
    }
    recs = [
        RecommendedAction(
            action_type=ActionType.CREATE_SUPPORT_TICKET,
            description="Create a support ticket",
            rationale="test",
            requires_approval=True,
            targets=[],
            parameters={},
        ),
    ]
    await ensure_thread(state["thread_id"], "test")
    _, action_rows = await persist_hitl_incident_and_actions(state, recs)
    action_id = uuid.UUID(action_rows[0]["id"])

    action, status, msg, executed_at = await approve_action_in_db(action_id, approved=True, notes=None)
    assert status == ActionStatus.EXECUTED
    assert executed_at is not None


async def test_reject_action(require_db):
    """Rejecting a pending action should set status to REJECTED."""
    from schemas.actions import RecommendedAction

    state = {
        "query": "reject test",
        "thread_id": str(uuid.uuid4()),
        "root_cause": None,
        "domain_findings": [],
        "incident_id": None,
    }
    recs = [
        RecommendedAction(
            action_type=ActionType.CREATE_SUPPORT_TICKET,
            description="will be rejected",
            rationale="test",
            requires_approval=True,
            targets=[],
            parameters={},
        ),
    ]
    await ensure_thread(state["thread_id"], "test")
    _, action_rows = await persist_hitl_incident_and_actions(state, recs)
    action_id = uuid.UUID(action_rows[0]["id"])

    action, status, msg, executed_at = await approve_action_in_db(action_id, approved=False, notes="not needed")
    assert status == ActionStatus.REJECTED
    assert executed_at is None


async def test_approve_nonexistent_raises(require_db):
    """Approving a nonexistent action should raise LookupError."""
    with pytest.raises(LookupError, match="not found"):
        await approve_action_in_db(uuid.uuid4(), approved=True, notes=None)


# ── get_pending_actions includes thread_id ────────────────────────────────────


async def test_pending_actions_include_thread_id(require_db):
    """Verify the new thread_id field is present in pending actions list."""
    from schemas.actions import RecommendedAction

    thread_id = str(uuid.uuid4())
    state = {
        "query": "thread_id visibility test",
        "thread_id": thread_id,
        "root_cause": None,
        "domain_findings": [],
        "incident_id": None,
    }
    recs = [
        RecommendedAction(
            action_type=ActionType.RESTOCK,
            description="check thread_id in pending list",
            rationale="test",
            requires_approval=True,
            targets=[],
            parameters={},
        ),
    ]
    await ensure_thread(thread_id, "test")
    await persist_hitl_incident_and_actions(state, recs)

    pending = await get_pending_actions()
    matching = [a for a in pending if a.get("thread_id") == thread_id]
    assert len(matching) >= 1
