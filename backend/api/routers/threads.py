"""GET /api/v1/threads — list threads and per-thread message history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import ThreadHistoryResponse, ThreadMessageItem, ThreadSummary
from db.pg_store import get_all_threads, get_thread_messages

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("", response_model=list[ThreadSummary])
async def list_threads() -> list[ThreadSummary]:
    """Return all threads ordered by most recently updated first."""
    rows = await get_all_threads()
    return [ThreadSummary(**r) for r in rows]


@router.get("/{thread_id}/history", response_model=ThreadHistoryResponse)
async def get_thread_history(thread_id: str) -> ThreadHistoryResponse:
    """Return all messages for a thread ordered by creation time."""
    messages = await get_thread_messages(thread_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadHistoryResponse(
        thread_id=thread_id,
        messages=[ThreadMessageItem(**m) for m in messages],
    )
