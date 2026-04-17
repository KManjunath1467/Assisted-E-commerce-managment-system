"""Integration test for the full LangGraph graph.

Requires:
- Seeded DB (python -m scripts.seed_data)
- Running MCP servers (sales:8001, inventory:8002, marketing:8003, cx:8004)
- Running LLM endpoint (DIAL_* env vars)
- Qdrant on localhost:6333

Run with: pytest backend/tests/test_graph.py -v
"""

import pytest
from langgraph.types import Command

from agents.graph import build_graph
from schemas.outputs import OperationsReport

pytestmark = pytest.mark.usefixtures("require_db", "require_mcp")


async def _run_graph(query: str, thread_id: str) -> dict:
    """Run the graph, auto-approving any HITL interrupt. Returns the full state dict."""
    graph = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    initial = {
        "query": query,
        "thread_id": thread_id,
        "time_range": None,
        "incident_id": None,
        "domains_to_run": [],
        "domain_findings": [],
        "root_cause": None,
        "reflection": None,
        "recommended_actions": [],
        "report": None,
        "requires_hitl": False,
        "requires_deep_analysis": True,
        "retry_count": 0,
    }

    result = await graph.ainvoke(initial, config=config)

    # Auto-approve HITL interrupts so tests run end-to-end without human input.
    if result.get("__interrupt__"):
        result = await graph.ainvoke(Command(resume={"approved": True}), config=config)

    return result


async def test_sales_drop_query_produces_report():
    """Full graph run: 'Why did sales drop yesterday?' should return an OperationsReport."""
    state = await _run_graph("Why did sales drop yesterday?", "test-integration-1")
    report: OperationsReport | None = state.get("report")
    domain_findings = state.get("domain_findings") or []

    assert report is not None, "Graph must produce a report"
    assert isinstance(report, OperationsReport)
    assert len(domain_findings) >= 1, "At least one domain finding expected"
    assert report.summary, "Summary must not be empty"
