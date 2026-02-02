"""POST /api/v1/query — invoke the operations assistant graph."""

from __future__ import annotations

import json
import logging
import os
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langgraph.graph import END

from api.schemas import QueryResponse
from core.settings import settings
from db.pg_store import cancel_pending_actions_for_thread, ensure_thread, persist_thread_messages
from schemas.common import default_time_range
from schemas.query import Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/stream")
async def run_query_stream(body: Query, request: Request) -> StreamingResponse:
    """Run the graph with SSE streaming — emits node-completion events followed
    by a terminal ``complete`` or ``pending_approval`` event carrying the full
    QueryResponse payload."""
    graph = request.app.state.graph

    thread_id = body.thread_id or str(uuid.uuid4())

    config: dict = build_config(thread_id)
    initial_state = build_initial_state(body, thread_id)

    # Ensure the thread row exists before streaming
    try:
        await ensure_thread(thread_id, body.query)
    except Exception:
        logger.warning("Failed to pre-create thread %s", thread_id, exc_info=True)

    # Clear stale interrupt from a previous HITL query on this thread.
    await _clear_stale_interrupt(graph, config, thread_id)

    return StreamingResponse(
        create_event_stream(graph, initial_state, config, thread_id, body.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def build_config(thread_id: str) -> dict:
    """Helper to build the graph config with Langfuse callback."""
    config: dict = {"configurable": {"thread_id": thread_id}}
    if os.environ.get("LANGFUSE_PUBLIC_KEY"):
        from langfuse.langchain import CallbackHandler

        config["callbacks"] = [CallbackHandler()]
        config["metadata"] = {"langfuse_session_id": thread_id}
    return config


def build_initial_state(body: Query, thread_id: str) -> dict:
    """Helper to build the initial graph state"""
    return {
        "query": body.query,
        "thread_id": thread_id,
        "time_range": body.time_range or default_time_range(),
        "incident_id": None,
        "domains_to_run": [],
        "domain_findings": [],
        "root_cause": None,
        "reflection": None,
        "recommended_actions": [],
        "report": None,
        "requires_hitl": False,
        "action_requested": False,
        "retry_count": 0,
        "conversation_history": [],
    }


async def create_event_stream(graph, initial_state, config, thread_id: str, query: str):
    """Helper to create the SSE event stream generator"""
    response: QueryResponse | None = None
    try:
        async for event in stream_updates(graph, initial_state, config, thread_id):
            yield event

        # Read final graph state from the checkpointer to build the response.
        state_snapshot = await graph.aget_state(config)
        response = parse_graph_state(state_snapshot, thread_id)

        if response is None:
            yield _sse_event("error", {"detail": "Graph did not produce a report."})
            return

        yield _sse_event(response.status, response.model_dump(mode="json"))
    finally:
        # Persist thread messages even if the client disconnects mid-stream.
        if response is not None:
            try:
                await persist_thread_messages(
                    thread_id,
                    user_content={"text": query},
                    assistant_content=response.model_dump(mode="json"),
                )
            except Exception:
                logger.warning("Thread persistence failed for thread %s (SSE)", thread_id, exc_info=True)


def parse_graph_state(state_snapshot, thread_id: str) -> QueryResponse | None:
    result = state_snapshot.values

    if state_snapshot.next:
        payload = _extract_interrupt_payload(state_snapshot.tasks)
        pending = payload.get("actions", []) if isinstance(payload, dict) else []

        return QueryResponse(
            status="pending_approval",
            thread_id=thread_id,
            pending_actions=pending,
        )

    report = result.get("report")
    if report is None:
        return None  # handled by caller (same as original behavior)

    return QueryResponse(
        status="complete",
        thread_id=thread_id,
        report=report,
    )


async def stream_updates(graph, initial_state, config, thread_id):
    try:
        async for update in graph.astream(initial_state, config=config, stream_mode="updates"):
            valid_nodes = _GRAPH_NODES.intersection(update.keys())
            for node_name in valid_nodes:
                yield _sse_event("node_complete", {"node": node_name})
    except Exception as exc:
        logger.exception("SSE stream failed for thread %s", thread_id)
        detail = str(exc) if settings.debug else "Internal processing error."
        yield _sse_event("error", {"detail": detail})
        return


# Known node names in the graph — used to filter streamed updates.
_GRAPH_NODES = frozenset(
    {
        "router",
        "orchestrator",
        "sales",
        "inventory",
        "marketing",
        "customer_support",
        "aggregator",
        "reflector",
        "hitl",
        "final_response",
    }
)


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _extract_interrupt_payload(tasks) -> dict:
    """Helper to extract interrupt payload from a list of graph tasks."""
    for task in tasks or ():
        interrupts = getattr(task, "interrupts", None)
        if interrupts:
            intr = interrupts[0]
            return intr.value if hasattr(intr, "value") else intr
    return {}


async def _clear_stale_interrupt(graph, config: dict, thread_id: str) -> None:
    """Prepare a thread for a fresh graph run.

    1. Reject any PENDING_APPROVAL actions left over from a previous HITL round
       (e.g. multi-action rounds where only some were approved, or rounds the
       user abandoned).  This runs unconditionally so ``hitl_node`` — which uses
       ``pending_only=True`` — won't mistake old actions for "already persisted".
    2. If the graph checkpoint is still interrupted / mid-execution, force it to
       END so the next ``ainvoke`` starts from START.
    """
    try:
        cancelled = await cancel_pending_actions_for_thread(thread_id)
        if cancelled:
            logger.info("Auto-cancelled %d orphaned pending action(s) for thread %s", cancelled, thread_id)

        snapshot = await graph.aget_state(config)
        if snapshot and snapshot.next:
            logger.warning(
                "Thread %s has stale graph state (next=%s). Force-completing before new query.",
                thread_id,
                snapshot.next,
            )
            await graph.aupdate_state(config, {}, as_node=END)
    except Exception:
        logger.warning(
            "Stale-state cleanup failed for thread %s",
            thread_id,
            exc_info=True,
        )
