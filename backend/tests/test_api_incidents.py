"""Tests for /api/v1/incidents endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests import FAKE_INCIDENT_ID, make_incident_dict

pytestmark = pytest.mark.asyncio


# ── GET /api/v1/incidents ─────────────────────────────────────────────────────


@patch("api.routers.incidents.get_all_incidents", new_callable=AsyncMock)
async def test_list_incidents(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = [make_incident_dict()]
    resp = await client.get("/api/v1/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == FAKE_INCIDENT_ID


@patch("api.routers.incidents.get_all_incidents", new_callable=AsyncMock)
async def test_list_incidents_empty(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = []
    resp = await client.get("/api/v1/incidents")
    assert resp.status_code == 200
    assert resp.json() == []


# ── GET /api/v1/incidents/{id} ────────────────────────────────────────────────


@patch("api.routers.incidents.get_incident_by_id", new_callable=AsyncMock)
async def test_get_incident_found(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = make_incident_dict()
    resp = await client.get(f"/api/v1/incidents/{FAKE_INCIDENT_ID}")
    assert resp.status_code == 200
    assert resp.json()["summary"] == "Low stock on Product A"


@patch("api.routers.incidents.get_incident_by_id", new_callable=AsyncMock)
async def test_get_incident_not_found(mock_get: AsyncMock, client: AsyncClient):
    mock_get.return_value = None
    resp = await client.get(f"/api/v1/incidents/{FAKE_INCIDENT_ID}")
    assert resp.status_code == 404


async def test_get_incident_invalid_id(client: AsyncClient):
    resp = await client.get("/api/v1/incidents/not-a-uuid")
    assert resp.status_code == 400


# ── PATCH /api/v1/incidents/{id}/resolve ──────────────────────────────────────


@patch("api.routers.incidents.resolve_incident_in_db", new_callable=AsyncMock)
async def test_resolve_incident(mock_resolve: AsyncMock, client: AsyncClient):
    resolved = make_incident_dict()
    resolved["status"] = "resolved"
    mock_resolve.return_value = resolved

    resp = await client.patch(
        f"/api/v1/incidents/{FAKE_INCIDENT_ID}/resolve",
        json={"resolution_summary": "Fixed by restocking."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


@patch("api.routers.incidents.resolve_incident_in_db", new_callable=AsyncMock)
async def test_resolve_incident_not_found(mock_resolve: AsyncMock, client: AsyncClient):
    mock_resolve.side_effect = LookupError("Incident not found.")
    resp = await client.patch(
        f"/api/v1/incidents/{FAKE_INCIDENT_ID}/resolve",
        json={},
    )
    assert resp.status_code == 404


@patch("api.routers.incidents.resolve_incident_in_db", new_callable=AsyncMock)
async def test_resolve_already_resolved(mock_resolve: AsyncMock, client: AsyncClient):
    mock_resolve.side_effect = ValueError("Incident is already resolved.")
    resp = await client.patch(
        f"/api/v1/incidents/{FAKE_INCIDENT_ID}/resolve",
        json={},
    )
    assert resp.status_code == 409
