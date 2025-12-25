"""LangGraph node functions for the e-commerce operations assistant."""

from __future__ import annotations

import logging
from functools import cache

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command, Send, interrupt

from agents._domain_builders import (
    build_cx_finding,
    build_inventory_finding,
    build_marketing_finding,
    build_sales_finding,
)
from agents.factory import create_agent
from agents.rules import build_recommendations
from agents.state import GraphState
from core.constants import DATA_START_DATE, MAX_RETRIES, REORDER_POINT
from db.pg_store import get_actions_by_thread, persist_hitl_incident_and_actions, save_incident
from schemas.analysis import DomainFinding, ReflectionResult, RootCauseAnalysis
from schemas.common import default_time_range
from schemas.outputs import OperationsReport

logger = logging.getLogger(__name__)


@cache
def _get_agent(name: str):
    return create_agent(name)


def _format_findings_text(findings: list[DomainFinding]) -> str:
    return "\n\n".join(f"[{f.domain.upper()}]\n{f.data.model_dump_json(indent=2)}" for f in findings)


async def router_node(state: GraphState) -> dict:
    """Classify the query and determine which domain agents to run."""
    _, results = await _get_agent("router").run(query=state["query"])
    intent = results[0][1]

    return {
        "domains_to_run": intent.domains_to_run,
        "intent_type": intent.intent_type,
        "is_meta": intent.is_meta,
        "action_requested": intent.action_requested,
        "retry_count": 0,
        "domain_findings": None,
        "recommended_actions": [],
        "requires_hitl": False,
    }


def orchestrator_node(state: GraphState) -> Command:
    if state.get("is_meta") or state.get("intent_type") == "out_of_scope":
        return Command(goto="final_response")

    domains = set(state["domains_to_run"])
    reflection = state.get("reflection")

    if reflection and reflection.needs_more_data and reflection.missing_domains:
        domains.update(reflection.missing_domains)

    sends = [Send(domain.value, state) for domain in domains]

    return Command(
        goto=sends if sends else "aggregator",
        update={"requires_deep_analysis": (state.get("intent_type") == "broad" or len(domains) > 1)},
    )


async def sales_node(state: GraphState) -> dict:
    """Run the sales agent and return a domain finding."""
    tr = state.get("time_range") or default_time_range()
    analysis_date = tr.start.date().isoformat()

    _, tool_results = await _get_agent("sales").run(
        query=state["query"],
        analysis_date=analysis_date,
        data_start_date=DATA_START_DATE,
        requires_deep_analysis=str(state.get("requires_deep_analysis", True)).lower(),
    )
    results = {name: result for name, result in tool_results}
    finding = build_sales_finding(results)
    return {"domain_findings": [finding] if finding else []}


async def inventory_node(state: GraphState) -> dict:
    """Run the inventory agent and return a domain finding."""
    tr = state.get("time_range") or default_time_range()
    analysis_date = tr.start.date().isoformat()

    _, tool_results = await _get_agent("inventory").run(
        query=state["query"],
        analysis_date=analysis_date,
        reorder_point=REORDER_POINT,
        requires_deep_analysis=str(state.get("requires_deep_analysis", True)).lower(),
    )
    results = {name: result for name, result in tool_results}
    finding = build_inventory_finding(results)
    return {"domain_findings": [finding] if finding else []}


async def marketing_node(state: GraphState) -> dict:
    """Run the marketing agent and return a domain finding."""
    _, tool_results = await _get_agent("marketing").run(
        query=state["query"],
        requires_deep_analysis=str(state.get("requires_deep_analysis", True)).lower(),
    )
    results = {name: result for name, result in tool_results}
    finding = build_marketing_finding(results)
    return {"domain_findings": [finding] if finding else []}


async def cx_node(state: GraphState) -> dict:
    """Run the customer support agent and return a domain finding."""
    tr = state.get("time_range") or default_time_range()
    analysis_date = tr.start.date().isoformat()

    _, tool_results = await _get_agent("customer_support").run(
        query=state["query"],
        analysis_date=analysis_date,
        requires_deep_analysis=str(state.get("requires_deep_analysis", True)).lower(),
    )
    results = {name: result for name, result in tool_results}
    finding = build_cx_finding(results)
    return {"domain_findings": [finding] if finding else []}


async def aggregator_node(state: GraphState) -> dict:
    """Produce a root cause analysis and recommendations from domain findings."""
    findings = state.get("domain_findings") or []
    requires_deep = state.get("requires_deep_analysis", True)
    action_requested = state.get("action_requested", False)

    # Always build recommendations from findings — even for targeted (non-deep)
    # queries, actionable signals (low stock, bad ROAS, etc.) should surface
    # suggestions when the data warrants it.
    recommendations = build_recommendations(findings, action_requested=action_requested, query=state.get("query", ""))

    if not findings and state.get("domains_to_run"):
        # Domain agents ran but returned nothing — nothing to aggregate.
        return {"root_cause": None, "recommended_actions": recommendations}

    findings_text = (
        _format_findings_text(findings) if findings else "No domain findings — this query does not require domain data."
    )

    if findings and not requires_deep and not action_requested:
        # Simple factual lookup with domain data — skip deep analysis.
        return {"root_cause": None, "recommended_actions": recommendations}

    _, results = await _get_agent("aggregator").run(
        query=state["query"],
        findings_text=findings_text,
    )

    # Extract the structured RootCauseAnalysis from captured results.
    root_cause: RootCauseAnalysis | None = None
    for name, result in results:
        if name == "__structured__" and isinstance(result, RootCauseAnalysis):
            root_cause = result
            break

    logger.info(
        "aggregator_node: built %d recommendations (action_requested=%s, requires_deep=%s)",
        len(recommendations),
        action_requested,
        requires_deep,
    )
    return {
        "root_cause": root_cause,
        "recommended_actions": recommendations,
    }


async def reflector_node(state: GraphState) -> dict:
    retry_count = state.get("retry_count", 0)

    if retry_count >= MAX_RETRIES:
        return {
            "reflection": ReflectionResult(
                is_complete=True,
                needs_more_data=False,
                missing_domains=[],
                confidence=state.get("root_cause").confidence if state.get("root_cause") else 0.5,
                action_required=False,
                issues={"system": "Max retries reached"},
            ),
            "retry_count": retry_count + 1,
        }

    root_cause = state.get("root_cause")
    root_cause_json = root_cause.model_dump_json(indent=2) if root_cause else "None"

    findings_text = _format_findings_text(state["domain_findings"]) if state["domain_findings"] else "None"

    _, results = await _get_agent("reflector").run(
        query=state["query"],
        domains_to_run=", ".join(d.value for d in state.get("domains_to_run", [])),
        retry_count=retry_count,
        root_cause_json=root_cause_json,
        findings_text=findings_text,
    )

    reflection: ReflectionResult = results[0][1]

    return {
        "reflection": reflection,
        "retry_count": retry_count + 1,
        # Treat action_requested as a guaranteed HITL signal — don't rely on
        # the LLM to re-derive it from the query text.
        "requires_hitl": reflection.action_required or state.get("action_requested", False),
    }


async def hitl_node(state: GraphState) -> dict:
    """Persist incident + action rows to DB, then pause for human approval.

    LangGraph re-executes the node from the top on resume, so we must guard
    against creating duplicate DB rows.  We check for existing pending actions
    tied to this thread — if they already exist we skip the persist and go
    straight to the interrupt (which returns the resume payload on the second
    call).
    """
    recommendations = state.get("recommended_actions", [])
    thread_id = state.get("thread_id")
    logger.info(
        "hitl_node: %d recommendations in state, requires_hitl=%s, action_requested=%s",
        len(recommendations),
        state.get("requires_hitl"),
        state.get("action_requested"),
    )

    # Check if *pending* actions for this thread already exist (i.e. we're
    # resuming a live interrupt).  Using pending_only=True ensures that old
    # approved/rejected actions from previous HITL rounds on the same thread
    # are ignored — otherwise the node would skip persisting and serve stale data.
    existing_actions = await get_actions_by_thread(thread_id, pending_only=True) if thread_id else []

    if existing_actions:
        # Resume path — actions already persisted on the first execution.
        logger.info(
            "hitl_node: found %d existing actions for thread %s, skipping persist", len(existing_actions), thread_id
        )
        incident_id = existing_actions[0]["incident_id"]
        action_rows = existing_actions
    else:
        incident_id, action_rows = await persist_hitl_incident_and_actions(state, recommendations)
        logger.info("hitl_node: persisted %d action rows, interrupting", len(action_rows))

    interrupt({"actions": action_rows})
    return {"incident_id": incident_id}


async def final_response_node(state: GraphState) -> dict:
    """Generate an OperationsReport and persist the incident to memory stores."""
    root_cause = state.get("root_cause")
    history = state.get("conversation_history") or []
    pairs = list(zip(history[::2], history[1::2], strict=False))
    conversation_context = (
        "\n".join(
            f"Turn {i + 1} — User: {human.content}\nAssistant: {ai.content}" for i, (human, ai) in enumerate(pairs[-5:])
        )
        or "No prior conversation."
    )

    # No domain findings and no root cause means either:
    # (a) the query is out-of-scope/greeting, or
    # (b) it's a meta-question about prior turns.
    if not state.get("domain_findings") and root_cause is None:
        # Let the LLM respond naturally. For meta queries, conversation_context
        # already contains the prior turns so the agent can reference them.
        _, results = await _get_agent("final_response").run(
            query=state["query"],
            intent_type=("meta" if state.get("is_meta") else state.get("intent_type", "out_of_scope")),
            requires_deep_analysis="false",
            is_complete="true",
            primary_cause="",
            confidence="",
            findings_text="None",
            actions_text="None",
            conversation_context=conversation_context,
        )
        summary = results[0][1]
        report = OperationsReport(
            query=state["query"],
            thread_id=state.get("thread_id"),
            incident_id=None,
            recommendations=[],
            summary=summary,
            requires_human_approval=False,
        )
        return {
            "report": report,
            "conversation_history": [
                HumanMessage(content=state["query"]),
                AIMessage(content=summary),
            ],
        }
    findings_text = _format_findings_text(state.get("domain_findings", []))
    if state.get("recommended_actions"):
        actions_text = "\n".join(
            f"  - {a.action_type.value}: {a.description}" for a in state.get("recommended_actions", [])
        )
    else:
        actions_text = "  None"

    _, results = await _get_agent("final_response").run(
        query=state["query"],
        intent_type=state.get("intent_type", "targeted"),
        primary_cause=(
            ", ".join(root_cause.primary_cause)
            if root_cause and isinstance(root_cause.primary_cause, list)
            else (root_cause.primary_cause if root_cause else "")
        ),
        confidence=str(root_cause.confidence) if root_cause else "",
        findings_text=findings_text,
        actions_text=actions_text,
        conversation_context=conversation_context,
        requires_deep_analysis=str(state.get("requires_deep_analysis", True)).lower(),
        is_complete=(str(not root_cause.is_incomplete).lower() if root_cause else "false"),
    )
    summary: str = results[0][1]

    # Persist incidents for:
    #  a) analytical queries with a root_cause (deep analysis path), OR
    #  b) any query that produced actionable recommendations requiring approval
    #     (e.g. a targeted stock-check that uncovered an out-of-stock product).
    # If hitl_node already created an incident (HITL path), reuse its ID.
    incident_id = state.get("incident_id")
    recommended_actions = state.get("recommended_actions", [])
    has_actionable = any(r.requires_approval for r in recommended_actions)
    if not incident_id and (state.get("requires_deep_analysis", True) and root_cause or has_actionable):
        incident_id = await save_incident(state)

    report = OperationsReport(
        query=state["query"],
        thread_id=state.get("thread_id"),
        incident_id=incident_id,
        recommendations=recommended_actions,
        summary=summary,
        requires_human_approval=any(r.requires_approval for r in recommended_actions),
    )

    return {
        "report": report,
        "incident_id": incident_id,
        "conversation_history": [
            HumanMessage(content=state["query"]),
            AIMessage(content=summary),
        ],
    }
