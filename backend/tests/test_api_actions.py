"""Tests for /api/v1/actions endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests import (
    FAKE_ACTION_ID,
    FAKE_THREAD_ID,
    make_action_dict,
)

pytestmark = pytest.mark.asyncio


# ── GET /api/v1/actions ───────────────────────────────────────────────────────


@patch("api.routers.actions.get_all_actions", new_callable=AsyncMock)
async def test_list_all_actions(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = [make_action_dict(), make_action_dict(status="executed")]
    resp = await client.get("/api/v1/actions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@patch("api.routers.actions.get_all_actions", new_callable=AsyncMock)
async def test_list_all_actions_empty(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = []
    resp = await client.get("/api/v1/actions")
    assert resp.status_code == 200
    assert resp.json() == []


# ── GET /api/v1/actions/pending ───────────────────────────────────────────────


@patch("api.routers.actions.get_pending_actions", new_callable=AsyncMock)
async def test_list_pending_returns_actions(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = [make_action_dict()]
    resp = await client.get("/api/v1/actions/pending")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["thread_id"] == FAKE_THREAD_ID


@patch("api.routers.actions.get_pending_actions", new_callable=AsyncMock)
async def test_list_pending_empty(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = []
    resp = await client.get("/api/v1/actions/pending")
    assert resp.status_code == 200
    assert resp.json() == []


# ── GET /api/v1/actions/{id} ──────────────────────────────────────────────────


@patch("api.routers.actions.get_action_by_id", new_callable=AsyncMock)
async def test_get_action_found(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = make_action_dict()
    resp = await client.get(f"/api/v1/actions/{FAKE_ACTION_ID}")
    assert resp.status_code == 200
    assert resp.json()["id"] == FAKE_ACTION_ID


@patch("api.routers.actions.get_action_by_id", new_callable=AsyncMock)
async def test_get_action_not_found(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = None
    resp = await client.get(f"/api/v1/actions/{FAKE_ACTION_ID}")
    assert resp.status_code == 404


async def test_get_action_invalid_id(client: AsyncClient):
    resp = await client.get("/api/v1/actions/not-a-uuid")
    assert resp.status_code == 400


# ── POST /api/v1/actions/{id}/approve ─────────────────────────────────────────


@patch("api.routers.actions.approve_action_in_db", new_callable=AsyncMock)
@patch("api.routers.actions.get_action_by_id", new_callable=AsyncMock)
async def test_approve_with_thread_id_resumes_graph(mock_get: AsyncMock, mock_approve: AsyncMock, client: AsyncClient):
    """When thread_id is provided, the graph should be resumed."""
    from db.models import Action

    mock_get.return_value = make_action_dict()

    action = Action()
    action.action_type = "restock"
    now = datetime.now(UTC)
    mock_approve.return_value = (action, "executed", "Restocked", now)

    resp = await client.post(
        f"/api/v1/actions/{FAKE_ACTION_ID}/approve",
        json={"approved": True, "thread_id": FAKE_THREAD_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "executed"

    # Verify graph.ainvoke was called (graph resume).
    client_app = client._transport.app  # type: ignore[attr-defined]
    client_app.state.graph.ainvoke.assert_called_once()


@patch("api.routers.actions.approve_action_in_db", new_callable=AsyncMock)
@patch("api.routers.actions.get_action_by_id", new_callable=AsyncMock)
async def test_approve_without_thread_id_skips_graph(mock_get: AsyncMock, mock_approve: AsyncMock, client: AsyncClient):
    """When thread_id is null, graph resume should be skipped."""
    from db.models import Action

    mock_get.return_value = make_action_dict()

    action = Action()
    action.action_type = "restock"
    mock_approve.return_value = (action, "executed", "Restocked", datetime.now(UTC))

    resp = await client.post(
        f"/api/v1/actions/{FAKE_ACTION_ID}/approve",
        json={"approved": True, "thread_id": None},
    )
    assert resp.status_code == 200

    client_app = client._transport.app  # type: ignore[attr-defined]
    client_app.state.graph.ainvoke.assert_not_called()


@patch("api.routers.actions.approve_action_in_db", new_callable=AsyncMock)
@patch("api.routers.actions.get_action_by_id", new_callable=AsyncMock)
async def test_reject_action(mock_get: AsyncMock, mock_approve: AsyncMock, client: AsyncClient):
    from db.models import Action

    mock_get.return_value = make_action_dict()

    action = Action()
    action.action_type = "restock"
    mock_approve.return_value = (action, "rejected", "Rejected by user", None)

    resp = await client.post(
        f"/api/v1/actions/{FAKE_ACTION_ID}/approve",
        json={"approved": False, "thread_id": FAKE_THREAD_ID, "notes": "Not needed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@patch("api.routers.actions.get_action_by_id", new_callable=AsyncMock)
async def test_approve_not_found(mock_get: AsyncMock, client: AsyncClient):
    """Validation check returns 404 before even touching approve_action_in_db."""
    mock_get.return_value = None
    resp = await client.post(
        f"/api/v1/actions/{FAKE_ACTION_ID}/approve",
        json={"approved": True},
    )
    assert resp.status_code == 404


@patch("api.routers.actions.get_action_by_id", new_callable=AsyncMock)
async def test_approve_wrong_status(mock_get: AsyncMock, client: AsyncClient):
    """Validation check returns 409 when action is not pending_approval."""
    mock_get.return_value = make_action_dict(status="executed")
    resp = await client.post(
        f"/api/v1/actions/{FAKE_ACTION_ID}/approve",
        json={"approved": True},
    )
    assert resp.status_code == 409


@patch("api.routers.actions.approve_action_in_db", new_callable=AsyncMock)
@patch("api.routers.actions.get_action_by_id", new_callable=AsyncMock)
async def test_graph_resume_failure_does_not_fail_request(
    mock_get: AsyncMock, mock_approve: AsyncMock, client: AsyncClient
):
    """Graph resume failure should be logged but not surface to API caller."""
    from db.models import Action

    mock_get.return_value = make_action_dict()

    action = Action()
    action.action_type = "restock"
    mock_approve.return_value = (action, "executed", "Restocked", datetime.now(UTC))

    # Make graph.ainvoke raise.
    client_app = client._transport.app  # type: ignore[attr-defined]
    client_app.state.graph.ainvoke.side_effect = RuntimeError("graph broke")

    resp = await client.post(
        f"/api/v1/actions/{FAKE_ACTION_ID}/approve",
        json={"approved": True, "thread_id": FAKE_THREAD_ID},
    )
    # Should still succeed — DB update is the source of truth.
    assert resp.status_code == 200
    assert resp.json()["status"] == "executed"
