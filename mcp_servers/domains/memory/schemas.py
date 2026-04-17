"""Schemas for past-incident memory search results."""

from datetime import datetime

from pydantic import BaseModel, Field


class PastIncident(BaseModel):
    incident_id: str = Field(..., description="Unique incident identifier")
    query: str = Field("", description="Original query that triggered the incident")
    summary: str = Field(..., description="Root cause summary from the incident")
    actions_taken: list[str] = Field(
        default_factory=list, description="Action types executed"
    )
    similarity: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score to the search query"
    )
    created_at: datetime = Field(..., description="When the incident was created (UTC)")


class PastIncidentSearchResult(BaseModel):
    kind: str = Field("memory", description="Discriminator for domain analysis union")
    incidents: list[PastIncident] = Field(
        default_factory=list, description="Matched past incidents"
    )
