"""Tests for /api/v1/query endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


FAKE_THREAD_ID = str(uuid.uuid4())


def _make_graph_result(*, pending: bool = False) -> dict:
    """Build a minimal graph result dict."""
    base = {
        "query": "check inventory",
        "thread_id": FAKE_THREAD_ID,
        "report": {
            "query": "check inventory",
            "thread_id": FAKE_THREAD_ID,
            "incident_id": None,
            "recommendations": [],
            "summary": "All good",
            "requires_human_approval": False,
            "generated_at": "2025-01-01T00:00:00Z",
        },
    }
    if pending:
        base["__interrupt__"] = [
            type(
                "Interrupt",
                (),
                {
                    "value": {
                        "actions": [
                            {
                                "id": str(uuid.uuid4()),
                                "incident_id": str(uuid.uuid4()),
                                "action_type": "restock",
                                "description": "Restock Product A",
                                "status": "pending_approval",
                                "created_at": "2025-01-01T00:00:00",
                                "executed_at": None,
                                "thread_id": FAKE_THREAD_ID,
                            }
                        ]
                    }
                },
            )()
        ]
    return base


# ── POST /api/v1/query ────────────────────────────────────────────────────────


@patch("api.routers.query.persist_thread_messages", new_callable=AsyncMock)
@patch("api.routers.query.ensure_thread", new_callable=AsyncMock)
async def test_sync_query_complete(mock_ensure: AsyncMock, mock_persist: AsyncMock, client: AsyncClient):
    """Sync query returning a complete report."""
    graph_mock: AsyncMock = client._transport.app.state.graph  # type: ignore[attr-defined]
    graph_mock.ainvoke.return_value = _make_graph_result()

    resp = await client.post(
        "/api/v1/query",
        json={"query": "check inventory"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "complete"
    assert data["report"]["summary"] == "All good"
    mock_ensure.assert_called()


@patch("api.routers.query.persist_thread_messages", new_callable=AsyncMock)
@patch("api.routers.query.ensure_thread", new_callable=AsyncMock)
async def test_sync_query_pending_approval(mock_ensure: AsyncMock, mock_persist: AsyncMock, client: AsyncClient):
    """Sync query that triggers HITL interrupt."""
    graph_mock: AsyncMock = client._transport.app.state.graph  # type: ignore[attr-defined]
    graph_mock.ainvoke.return_value = _make_graph_result(pending=True)

    resp = await client.post(
        "/api/v1/query",
        json={"query": "restock products"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending_approval"


# ── POST /api/v1/query/stream ─────────────────────────────────────────────────


@patch("api.routers.query.persist_thread_messages", new_callable=AsyncMock)
@patch("api.routers.query.ensure_thread", new_callable=AsyncMock)
async def test_stream_query_returns_sse(mock_ensure: AsyncMock, mock_persist: AsyncMock, client: AsyncClient):
    """SSE endpoint returns text/event-stream content type."""
    graph_mock: AsyncMock = client._transport.app.state.graph  # type: ignore[attr-defined]

    # astream returns an async iterator of node updates
    async def fake_astream(*a, **kw):
        yield {"router_node": {}}
        yield {"final_response_node": _make_graph_result()}

    graph_mock.astream = fake_astream

    # aget_state is called after the stream to build the final response
    state_snapshot = AsyncMock()
    state_snapshot.values = _make_graph_result()
    state_snapshot.next = ()  # not suspended
    state_snapshot.tasks = ()
    graph_mock.aget_state = AsyncMock(return_value=state_snapshot)

    resp = await client.post(
        "/api/v1/query/stream",
        json={"query": "check inventory"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
