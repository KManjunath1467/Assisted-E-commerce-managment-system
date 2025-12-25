"""POST /api/v1/query — invoke the operations assistant graph."""

from __future__ import annotations

import json
import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.graph import END

from api.schemas import QueryResponse
from core.settings import settings
from db.pg_store import cancel_pending_actions_for_thread, ensure_thread, persist_thread_messages
from schemas.common import default_time_range
from schemas.query import Query

logger = logging.getLogger(__name__)


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


router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def run_query(body: Query, request: Request) -> QueryResponse:
    """Run an e-commerce operations query through the multi-agent graph."""
    # Graph is initialised in lifespan and stored on app.state — thread-safe.
    graph = request.app.state.graph

    thread_id = body.thread_id or str(uuid.uuid4())
    config: dict = {"configurable": {"thread_id": thread_id}}

    # Attach Langfuse callback when tracing is configured.
    # langfuse_session_id groups the initial query and any HITL resume into one session.
    if os.environ.get("LANGFUSE_PUBLIC_KEY"):
        from langfuse.langchain import CallbackHandler

        config["callbacks"] = [CallbackHandler()]
        config["metadata"] = {"langfuse_session_id": thread_id}

    initial_state = {
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

    # Ensure the thread row exists before the graph runs — the HITL node
    # inserts actions with a FK to threads, so the row must be present.
    try:
        await ensure_thread(thread_id, body.query)
    except Exception:
        logger.warning("Failed to pre-create thread %s", thread_id, exc_info=True)

    # If a previous HITL query left the graph interrupted/incomplete, clear
    # the stale checkpoint so this query starts fresh from START.
    await _clear_stale_interrupt(graph, config, thread_id)

    try:
        result = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.exception("Graph invocation failed for thread %s", thread_id)
        detail = str(exc) if settings.debug else "Internal processing error. Please try again."
        raise HTTPException(status_code=500, detail=detail) from exc

    # Detect HITL interrupt: interrupt() pauses the graph and sets __interrupt__
    if result.get("__interrupt__"):
        interrupt_data = result["__interrupt__"][0]
        payload = interrupt_data.value if hasattr(interrupt_data, "value") else interrupt_data
        pending = payload.get("actions", []) if isinstance(payload, dict) else []
        response = QueryResponse(
            status="pending_approval",
            thread_id=thread_id,
            pending_actions=pending,
        )
    else:
        report = result.get("report")
        if report is None:
            raise HTTPException(status_code=500, detail="Graph did not produce a report.")
        response = QueryResponse(status="complete", thread_id=thread_id, report=report)

    # Persist thread messages for sidebar history (thread row already ensured above).
    try:
        await persist_thread_messages(
            thread_id,
            user_content={"text": body.query},
            assistant_content=response.model_dump(mode="json"),
        )
    except Exception:
        # Thread persistence failing must never break the main response, but
        # log so we have visibility in production.
        logger.warning("Thread persistence failed for thread %s", thread_id, exc_info=True)

    return response


# ── SSE streaming variant ───────────────────────────────────────────────────

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


@router.post("/stream")
async def run_query_stream(body: Query, request: Request) -> StreamingResponse:
    """Run the graph with SSE streaming — emits node-completion events followed
    by a terminal ``complete`` or ``pending_approval`` event carrying the full
    QueryResponse payload."""
    graph = request.app.state.graph

    thread_id = body.thread_id or str(uuid.uuid4())
    config: dict = {"configurable": {"thread_id": thread_id}}

    if os.environ.get("LANGFUSE_PUBLIC_KEY"):
        from langfuse.langchain import CallbackHandler

        config["callbacks"] = [CallbackHandler()]
        config["metadata"] = {"langfuse_session_id": thread_id}

    initial_state = {
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

    # Ensure the thread row exists before streaming — HITL node needs the FK.
    try:
        await ensure_thread(thread_id, body.query)
    except Exception:
        logger.warning("Failed to pre-create thread %s", thread_id, exc_info=True)

    # Clear stale interrupt from a previous HITL query on this thread.
    await _clear_stale_interrupt(graph, config, thread_id)

    async def _event_stream():
        try:
            async for update in graph.astream(initial_state, config=config, stream_mode="updates"):
                for node_name in update:
                    if node_name in _GRAPH_NODES:
                        yield _sse_event("node_complete", {"node": node_name})
        except Exception as exc:
            logger.exception("SSE stream failed for thread %s", thread_id)
            detail = str(exc) if settings.debug else "Internal processing error."
            yield _sse_event("error", {"detail": detail})
            return

        # Read final graph state from the checkpointer to build the response.
        state_snapshot = await graph.aget_state(config)
        result = state_snapshot.values

        if state_snapshot.next:
            # Graph is suspended (HITL interrupt).
            tasks = state_snapshot.tasks or ()
            payload: dict = {}
            for task in tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    intr = task.interrupts[0]
                    payload = intr.value if hasattr(intr, "value") else intr
                    break
            pending = payload.get("actions", []) if isinstance(payload, dict) else []
            response = QueryResponse(
                status="pending_approval",
                thread_id=thread_id,
                pending_actions=pending,
            )
        else:
            report = result.get("report")
            if report is None:
                yield _sse_event("error", {"detail": "Graph did not produce a report."})
                return
            response = QueryResponse(
                status="complete",
                thread_id=thread_id,
                report=report,
            )

        # Stream the report summary word-by-word as token events before
        # the terminal complete/pending_approval event so the frontend can
        # render text progressively.
        if response.status == "complete" and response.report:
            words = response.report.summary.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == 0 else " " + word
                yield _sse_event("token", {"content": chunk})

        yield _sse_event(response.status, response.model_dump(mode="json"))

        # Persist thread messages (thread row already ensured before streaming).
        try:
            await persist_thread_messages(
                thread_id,
                user_content={"text": body.query},
                assistant_content=response.model_dump(mode="json"),
            )
        except Exception:
            logger.warning("Thread persistence failed for thread %s (SSE)", thread_id, exc_info=True)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
