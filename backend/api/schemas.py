"""HTTP-layer schemas for the e-commerce operations assistant API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from core.enums import ActionStatus, ActionType, IncidentStatus
from schemas.outputs import OperationsReport


class ThreadSummary(BaseModel):
    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ThreadMessageItem(BaseModel):
    id: uuid.UUID
    role: str
    content: dict[str, Any]
    created_at: datetime


class ThreadHistoryResponse(BaseModel):
    thread_id: str
    messages: list[ThreadMessageItem]


class PendingActionResponse(BaseModel):
    """Typed response for action records (replaces raw dict)."""

    id: str
    incident_id: str
    action_type: ActionType
    description: str | None = None
    status: ActionStatus
    created_at: str
    executed_at: str | None = None
    thread_id: str | None = None


class IncidentResponse(BaseModel):
    """Typed response for incident records (replaces raw dict)."""

    id: str
    summary: str | None = None
    status: IncidentStatus
    created_at: str
    resolved_at: str | None = None
    signals: dict[str, Any] | None = None
    resolution_summary: str | None = None
    actions: list[PendingActionResponse] = []


class QueryResponse(BaseModel):
    """API response for POST /api/v1/query.

    ``status="complete"`` → ``report`` is populated.
    ``status="pending_approval"`` → graph paused for HITL; ``pending_actions``
    lists actions awaiting human approval and ``thread_id`` must be echoed back
    to ``POST /api/v1/actions/{id}/approve`` to resume the graph.
    """

    status: Literal["complete", "pending_approval"]
    thread_id: str
    report: OperationsReport | None = None
    pending_actions: list[PendingActionResponse] | None = None
