"""Shared test constants and factory helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

FAKE_INCIDENT_ID = str(uuid.uuid4())
FAKE_ACTION_ID = str(uuid.uuid4())
FAKE_THREAD_ID = str(uuid.uuid4())
_NOW = datetime.now(UTC)


def make_action_dict(
    *,
    action_id: str = FAKE_ACTION_ID,
    incident_id: str = FAKE_INCIDENT_ID,
    thread_id: str | None = FAKE_THREAD_ID,
    status: str = "pending_approval",
) -> dict:
    return {
        "id": action_id,
        "incident_id": incident_id,
        "action_type": "restock",
        "description": "Restock Product A",
        "status": status,
        "created_at": _NOW.isoformat(),
        "executed_at": None,
        "thread_id": thread_id,
    }


def make_incident_dict(*, incident_id: str = FAKE_INCIDENT_ID) -> dict:
    return {
        "id": incident_id,
        "summary": "Low stock on Product A",
        "status": "open",
        "created_at": _NOW.isoformat(),
        "resolved_at": None,
        "signals": {"query": "check inventory"},
        "resolution_summary": None,
        "actions": [make_action_dict()],
    }
