"""Incidents management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.schemas import IncidentResponse
from db.pg_store import (
    get_all_incidents,
    get_incident_by_id,
    resolve_incident_in_db,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


class ResolveBody(BaseModel):
    resolution_summary: str | None = None


@router.get("", response_model=list[IncidentResponse])
async def list_incidents() -> list[dict]:
    """List all incidents ordered by most recent, with their actions."""
    return await get_all_incidents()


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str) -> dict:
    """Get a single incident with all its actions."""
    try:
        iid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident_id format.") from None

    result = await get_incident_by_id(iid)
    if result is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return result


@router.patch("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(incident_id: str, body: ResolveBody | None = None) -> dict:
    """Mark an incident as resolved. Rejects any still-pending actions."""
    try:
        iid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident_id format.") from None

    try:
        return await resolve_incident_in_db(
            iid,
            resolution_summary=(body.resolution_summary if body else None),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
