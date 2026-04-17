from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core.enums import ActionStatus, ActionType


class RecommendedAction(BaseModel):
    action_type: ActionType = Field(..., description="Type of action to perform")
    description: str = Field(..., description="Human-readable description of the action")
    rationale: str = Field(..., description="Why this action is recommended")
    requires_approval: bool = Field(..., description="Whether this action requires human approval before execution")
    targets: list[str] = Field(
        default_factory=list,
        description="Target identifiers (product IDs, campaign IDs, etc.)",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters (e.g., {'discount_pct': 10, 'restock_qty': 500})",
    )


class ActionApprovalResponse(BaseModel):
    approved: bool = Field(..., description="Whether the action was approved")
    approved_by: str | None = Field(None, description="Identifier of the approving user")
    notes: str | None = Field(None, description="Optional notes from the approver")
    thread_id: str | None = Field(None, description="LangGraph thread ID — required to resume the HITL graph")


class ActionExecutionResult(BaseModel):
    action_type: ActionType = Field(..., description="The executed action type")
    status: ActionStatus = Field(..., description="Execution status")
    message: str = Field(..., description="Human-readable result or error message")
    executed_at: datetime | None = Field(None, description="When execution completed (UTC)")
