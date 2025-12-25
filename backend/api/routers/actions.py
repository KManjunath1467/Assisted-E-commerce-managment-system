"""Action HITL approval endpoints."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Request
from langgraph.types import Command

from api.schemas import PendingActionResponse
from db.pg_store import approve_action_in_db, get_action_by_id, get_all_actions, get_pending_actions
from schemas.actions import ActionApprovalResponse, ActionExecutionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=list[PendingActionResponse])
async def list_all_actions() -> list[dict]:
    """List all actions regardless of status, most recent first."""
    return await get_all_actions()


@router.get("/pending", response_model=list[PendingActionResponse])
async def list_pending_actions() -> list[dict]:
    """List all actions with PENDING_APPROVAL status."""
    return await get_pending_actions()


@router.get("/{action_id}", response_model=PendingActionResponse)
async def get_action(action_id: str) -> dict:
    """Fetch a single action by ID (any status)."""
    try:
        aid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action_id format.") from None
    action = await get_action_by_id(aid)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found.")
    return action


@router.post("/{action_id}/approve", response_model=ActionExecutionResult)
async def approve_action(action_id: str, body: ActionApprovalResponse, request: Request) -> ActionExecutionResult:
    """Approve or reject a pending action.

    If ``body.thread_id`` is provided the LangGraph thread is resumed so the
    graph can proceed to ``final_response_node`` and save the incident.

    **Ordering matters**: the graph is resumed *before* the DB status is
    updated.  LangGraph re-executes ``hitl_node`` from the top on resume, and
    the node uses ``pending_only=True`` to decide whether to create new action
    rows or skip.  If we updated the DB first, the action would no longer be
    ``PENDING_APPROVAL`` and the node would mistakenly create duplicates.
    """
    try:
        aid = uuid.UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action_id format.") from None

    # Lightweight validation — ensure the action exists and is still pending
    # before we attempt the (expensive) graph resume.
    action_check = await get_action_by_id(aid)
    if action_check is None:
        raise HTTPException(status_code=404, detail="Action not found.")
    if action_check["status"] != "pending_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Action is not pending approval (current status: {action_check['status']}).",
        )

    # Resume the LangGraph thread FIRST — while the action is still
    # PENDING_APPROVAL in the database so hitl_node correctly identifies
    # this as a resume (not a fresh HITL round on the same thread).
    # On resume, execute_approved_actions_node will call the MCP write tool
    # inside the graph (approved path only).
    if body.thread_id:
        try:
            graph = request.app.state.graph
            config: dict = {"configurable": {"thread_id": body.thread_id}}

            if os.environ.get("LANGFUSE_PUBLIC_KEY"):
                from langfuse.langchain import CallbackHandler

                config["callbacks"] = [CallbackHandler()]
                config["metadata"] = {"langfuse_session_id": body.thread_id}

            await graph.ainvoke(
                Command(resume={"approved": body.approved, "action_id": action_id}),
                config=config,
            )
        except Exception as exc:
            # Graph resume failed — proceed to DB update anyway so the action
            # doesn't stay pending.  _clear_stale_interrupt will tidy the graph
            # state on the next query.
            logger.warning(
                "LangGraph resume failed for thread %s after action %s: %s",
                body.thread_id,
                action_id,
                exc,
            )

    try:
        action, final_status, msg, executed_at = await approve_action_in_db(aid, body.approved, body.notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ActionExecutionResult(
        action_type=action.action_type,
        status=final_status,
        message=msg,
        executed_at=executed_at,
    )
