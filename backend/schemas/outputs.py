from datetime import UTC, datetime

from pydantic import BaseModel, Field

from schemas.actions import RecommendedAction


class OperationsReport(BaseModel):
    query: str = Field(..., description="Original user query this report addresses")
    thread_id: str | None = Field(None, description="Conversation thread ID")
    incident_id: str | None = Field(None, description="Linked incident ID in the database")
    recommendations: list[RecommendedAction] = Field(
        default_factory=list,
        description="Recommended actions to address identified issues",
    )
    summary: str = Field(..., description="Executive summary of findings and recommendations")
    requires_human_approval: bool = Field(
        ...,
        description="Whether any recommended action requires human approval before execution",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this report was generated (UTC)",
    )
