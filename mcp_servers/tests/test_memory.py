"""Unit tests for the memory domain (past-incident search).

All external I/O (Qdrant, SentenceTransformer) is mocked so these run
without a live vector store or model download.

Run:  cd mcp_servers && uv run pytest tests/test_memory.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domains.memory.tools import search_past_incidents


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_qdrant_point(
    incident_id: str,
    summary: str,
    score: float,
    actions_taken: list[str] | None = None,
) -> MagicMock:
    """Create a fake Qdrant ScoredPoint with the expected payload structure."""
    point = MagicMock()
    point.score = score
    point.payload = {
        "incident_id": incident_id,
        "query": f"query for {incident_id}",
        "summary": summary,
        "actions_taken": actions_taken or [],
        "created_at": datetime.now(UTC).isoformat(),
    }
    return point


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_module_globals():
    """Reset the module-level singletons between tests."""
    import domains.memory.tools as mem

    orig_model = mem._model
    orig_client = mem._client
    yield
    mem._model = orig_model
    mem._client = orig_client


# ── Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_matched_incidents():
    """Happy path: Qdrant returns two points, both mapped to PastIncident."""
    points = [
        _make_qdrant_point("inc-1", "Revenue drop due to stockout", 0.92),
        _make_qdrant_point("inc-2", "Shipping delay spike", 0.78, ["create_support_ticket"]),
    ]

    query_result = MagicMock()
    query_result.points = points

    mock_model = MagicMock()
    mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    mock_client = MagicMock()
    mock_client.query_points = AsyncMock(return_value=query_result)

    with (
        patch("domains.memory.tools._get_model", return_value=mock_model),
        patch("domains.memory.tools._get_client", return_value=mock_client),
        patch("domains.memory.tools._encode_async", return_value=[0.1] * 384),
    ):
        result = await search_past_incidents("sudden revenue drop", limit=2)

    assert result.kind == "memory"
    assert len(result.incidents) == 2
    assert result.incidents[0].incident_id == "inc-1"
    assert result.incidents[0].similarity == pytest.approx(0.92)
    assert result.incidents[1].actions_taken == ["create_support_ticket"]


@pytest.mark.asyncio
async def test_returns_empty_on_connectivity_error():
    """Qdrant connectivity errors are caught and return empty results."""
    mock_model = MagicMock()
    mock_client = MagicMock()
    mock_client.query_points = AsyncMock(side_effect=ConnectionError("Qdrant unreachable"))

    with (
        patch("domains.memory.tools._get_model", return_value=mock_model),
        patch("domains.memory.tools._get_client", return_value=mock_client),
        patch("domains.memory.tools._encode_async", return_value=[0.1] * 384),
    ):
        result = await search_past_incidents("any query")

    assert result.incidents == []


@pytest.mark.asyncio
async def test_returns_empty_on_timeout():
    """TimeoutError (e.g. slow vector store) returns empty results, not a crash."""
    mock_model = MagicMock()
    mock_client = MagicMock()
    mock_client.query_points = AsyncMock(side_effect=TimeoutError("timed out"))

    with (
        patch("domains.memory.tools._get_model", return_value=mock_model),
        patch("domains.memory.tools._get_client", return_value=mock_client),
        patch("domains.memory.tools._encode_async", return_value=[0.1] * 384),
    ):
        result = await search_past_incidents("any query")

    assert result.incidents == []


@pytest.mark.asyncio
async def test_unexpected_errors_propagate():
    """Non-connectivity errors (e.g. encoding bug) are NOT silently swallowed."""
    mock_model = MagicMock()
    mock_client = MagicMock()
    mock_client.query_points = AsyncMock(side_effect=ValueError("schema mismatch"))

    with (
        patch("domains.memory.tools._get_model", return_value=mock_model),
        patch("domains.memory.tools._get_client", return_value=mock_client),
        patch("domains.memory.tools._encode_async", return_value=[0.1] * 384),
    ):
        with pytest.raises(ValueError, match="schema mismatch"):
            await search_past_incidents("any query")


@pytest.mark.asyncio
async def test_empty_results_from_qdrant():
    """Zero vector matches returns a valid empty result, not an error."""
    query_result = MagicMock()
    query_result.points = []

    mock_model = MagicMock()
    mock_client = MagicMock()
    mock_client.query_points = AsyncMock(return_value=query_result)

    with (
        patch("domains.memory.tools._get_model", return_value=mock_model),
        patch("domains.memory.tools._get_client", return_value=mock_client),
        patch("domains.memory.tools._encode_async", return_value=[0.1] * 384),
    ):
        result = await search_past_incidents("no match query")

    assert result.incidents == []
    assert result.kind == "memory"


@pytest.mark.asyncio
async def test_list_summary_payload_joined():
    """summary stored as a list in the payload is joined to a string."""
    point = MagicMock()
    point.score = 0.85
    point.payload = {
        "incident_id": "inc-3",
        "query": "q",
        "summary": ["Revenue", "dropped", "20%"],
        "actions_taken": [],
        "created_at": datetime.now(UTC).isoformat(),
    }

    query_result = MagicMock()
    query_result.points = [point]

    mock_model = MagicMock()
    mock_client = MagicMock()
    mock_client.query_points = AsyncMock(return_value=query_result)

    with (
        patch("domains.memory.tools._get_model", return_value=mock_model),
        patch("domains.memory.tools._get_client", return_value=mock_client),
        patch("domains.memory.tools._encode_async", return_value=[0.1] * 384),
    ):
        result = await search_past_incidents("revenue drop")

    assert result.incidents[0].summary == "Revenue, dropped, 20%"


@pytest.mark.asyncio
async def test_limit_passed_to_qdrant():
    """The limit argument is forwarded to Qdrant's query_points call."""
    query_result = MagicMock()
    query_result.points = []

    mock_model = MagicMock()
    mock_client = MagicMock()
    mock_client.query_points = AsyncMock(return_value=query_result)

    with (
        patch("domains.memory.tools._get_model", return_value=mock_model),
        patch("domains.memory.tools._get_client", return_value=mock_client),
        patch("domains.memory.tools._encode_async", return_value=[0.1] * 384),
    ):
        await search_past_incidents("test", limit=5)

    mock_client.query_points.assert_called_once()
    call_kwargs = mock_client.query_points.call_args.kwargs
    assert call_kwargs.get("limit") == 5
