"""Contract tests: validate backend response schemas match frontend types.

These are cheap, fast tests that catch field-level drift between the API layer
and the frontend type definitions without requiring a running server or DB.
"""

from __future__ import annotations

from domains.inventory.schemas import InventoryAnalysis, StockLevel

from api.schemas import (
    IncidentResponse,
    PendingActionResponse,
    QueryResponse,
)
from core.enums import ActionStatus, ActionType, IncidentStatus
from schemas.actions import ActionExecutionResult, RecommendedAction
from schemas.analysis import (
    CrossDomainCorrelation,
    DomainFinding,
    RootCauseAnalysis,
)
from schemas.outputs import OperationsReport

# ─── PendingActionResponse ↔ frontend PendingAction ─────────────────────────


def test_pending_action_response_fields():
    """PendingActionResponse must have exactly the fields the frontend expects."""
    expected = {
        "id",
        "incident_id",
        "action_type",
        "description",
        "status",
        "created_at",
        "executed_at",
        "thread_id",
    }
    actual = set(PendingActionResponse.model_fields.keys())
    assert actual == expected, f"extra={actual - expected}, missing={expected - actual}"


def test_pending_action_response_roundtrip():
    obj = PendingActionResponse(
        id="abc",
        incident_id="def",
        action_type=ActionType.RESTOCK,
        description="Restock widget",
        status=ActionStatus.PENDING_APPROVAL,
        created_at="2026-04-08T00:00:00+00:00",
        executed_at=None,
    )
    data = obj.model_dump(mode="json")
    assert data["action_type"] == "restock"
    assert data["status"] == "pending_approval"
    assert data["executed_at"] is None


# ─── IncidentResponse ↔ frontend Incident ───────────────────────────────────


def test_incident_response_fields():
    expected = {
        "id",
        "summary",
        "status",
        "created_at",
        "resolved_at",
        "signals",
        "resolution_summary",
        "actions",
    }
    actual = set(IncidentResponse.model_fields.keys())
    assert actual == expected, f"extra={actual - expected}, missing={expected - actual}"


def test_incident_response_with_actions():
    action = PendingActionResponse(
        id="a1",
        incident_id="i1",
        action_type=ActionType.PAUSE_CAMPAIGN,
        description="Pause campaign",
        status=ActionStatus.EXECUTED,
        created_at="2026-04-08T00:00:00+00:00",
        executed_at="2026-04-08T01:00:00+00:00",
    )
    inc = IncidentResponse(
        id="i1",
        summary="Test incident",
        status=IncidentStatus.OPEN,
        created_at="2026-04-08T00:00:00+00:00",
        actions=[action],
    )
    data = inc.model_dump(mode="json")
    assert data["status"] == "open"
    assert len(data["actions"]) == 1
    assert data["actions"][0]["action_type"] == "pause_campaign"


# ─── QueryResponse ↔ frontend QueryResponse ────────────────────────────────


def test_query_response_complete():
    report = OperationsReport(
        query="test",
        summary="All good",
        requires_human_approval=False,
    )
    resp = QueryResponse(status="complete", thread_id="t1", report=report)
    data = resp.model_dump(mode="json")
    assert data["status"] == "complete"
    assert data["report"]["summary"] == "All good"
    assert data["pending_actions"] is None


def test_query_response_pending():
    action = PendingActionResponse(
        id="a1",
        incident_id="i1",
        action_type=ActionType.RESTOCK,
        status=ActionStatus.PENDING_APPROVAL,
        created_at="2026-04-08T00:00:00+00:00",
    )
    resp = QueryResponse(
        status="pending_approval",
        thread_id="t1",
        pending_actions=[action],
    )
    data = resp.model_dump(mode="json")
    assert data["status"] == "pending_approval"
    assert data["report"] is None
    assert len(data["pending_actions"]) == 1


# ─── ActionExecutionResult ↔ frontend ActionExecutionResult ────────────────


def test_action_execution_result_fields():
    expected = {"action_type", "status", "message", "executed_at"}
    actual = set(ActionExecutionResult.model_fields.keys())
    assert actual == expected


# ─── OperationsReport ↔ frontend OperationsReport ──────────────────────────


def test_operations_report_fields():
    expected = {
        "query",
        "thread_id",
        "incident_id",
        "recommendations",
        "summary",
        "requires_human_approval",
        "generated_at",
    }
    actual = set(OperationsReport.model_fields.keys())
    assert actual == expected


# ─── RecommendedAction ↔ frontend RecommendedAction ────────────────────────


def test_recommended_action_fields():
    expected = {
        "action_type",
        "description",
        "rationale",
        "requires_approval",
        "targets",
        "parameters",
    }
    actual = set(RecommendedAction.model_fields.keys())
    assert actual == expected


# ─── InventoryAnalysis ↔ frontend InventoryAnalysis ────────────────────────


def test_inventory_analysis_fields():
    expected = {
        "kind",
        "stock_levels",
        "stockout_missed_views",
        "estimated_sales_impact",
        "insights",
    }
    actual = set(InventoryAnalysis.model_fields.keys())
    assert actual == expected, f"extra={actual - expected}, missing={expected - actual}"


def test_stock_level_has_unit_price():
    expected = {
        "product",
        "quantity",
        "unit_price",
        "reorder_point",
        "days_until_stockout",
        "is_out_of_stock",
    }
    actual = set(StockLevel.model_fields.keys())
    assert actual == expected


# ─── RootCauseAnalysis ↔ frontend RootCauseAnalysis ────────────────────────


def test_root_cause_analysis_fields():
    expected = {
        "is_incomplete",
        "primary_cause",
        "contributing_factors",
        "correlations",
        "evidence",
        "confidence",
    }
    actual = set(RootCauseAnalysis.model_fields.keys())
    assert actual == expected


# ─── DomainFinding ↔ frontend DomainFinding ────────────────────────────────


def test_domain_finding_fields():
    expected = {"domain", "severity", "data"}
    actual = set(DomainFinding.model_fields.keys())
    assert actual == expected


# ─── CrossDomainCorrelation ↔ frontend CrossDomainCorrelation ──────────────


def test_cross_domain_correlation_fields():
    expected = {"description", "evidence"}
    actual = set(CrossDomainCorrelation.model_fields.keys())
    assert actual == expected


# ─── SSE stream event shapes ────────────────────────────────────────────────


def test_sse_event_format():
    """Verify the _sse_event helper produces valid SSE text."""
    from api.routers.query import _sse_event

    result = _sse_event("node_complete", {"node": "sales"})
    assert result.startswith("event: node_complete\n")
    assert "data: " in result
    assert result.endswith("\n\n")


def test_query_response_complete_serializes_for_sse():
    """QueryResponse for a complete result must serialize cleanly for SSE."""
    report = OperationsReport(
        query="test",
        summary="Summary text",
        requires_human_approval=False,
    )
    resp = QueryResponse(status="complete", thread_id="t1", report=report)
    data = resp.model_dump(mode="json")
    # These are the keys the frontend StreamEvent parser expects.
    assert "status" in data
    assert "thread_id" in data
    assert "report" in data
    assert data["report"]["summary"] == "Summary text"
