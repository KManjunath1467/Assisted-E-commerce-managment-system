from domains.common import TimeRange
from pydantic import BaseModel, Field


class Query(BaseModel):
    query: str = Field(..., description="The e-commerce operation query")
    thread_id: str | None = Field(None, description="Conversation thread ID for continuity")
    time_range: TimeRange | None = Field(None, description="Optional time range to scope the analysis")
