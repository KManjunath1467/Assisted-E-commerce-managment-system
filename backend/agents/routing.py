"""Routing helpers for the e-commerce operations assistant graph.

Kept separate from nodes.py so graph topology logic (which node runs next)
is not mixed with node implementation (what a node does).
"""

from __future__ import annotations

from agents.state import GraphState
from core.constants import MAX_RETRIES


def route_after_aggregator(state: GraphState) -> str:
    """Conditional edge: decide what follows the aggregator node.

    - Simple factual queries (requires_deep_analysis=False, action_requested=False)
      skip the reflector entirely and go straight to the final response.
    - Analytical queries and action-requested queries proceed to the reflector,
      which validates the analysis and guards the HITL path.
    """
    if state.get("requires_deep_analysis", True) or state.get("action_requested", False):
        return "reflector"
    return "final_response"


def route_after_reflector(state: GraphState) -> str:
    """Conditional edge: decide what follows the reflector node.

    - Loop back to orchestrator for another analysis pass if the reflector
      flagged missing data and we have retries remaining.
    - Go to HITL if any recommended action requires human approval.
    - Otherwise proceed directly to the final response.
    """
    reflection = state.get("reflection")
    if reflection and reflection.needs_more_data and state.get("retry_count", 0) < MAX_RETRIES:
        return "orchestrator"
    if state.get("requires_hitl") and state.get("action_requested"):
        # Guard: only go to HITL when there are actual recommendations to show.
        # If recommendations is empty (data doesn't warrant action), fall through
        # to final_response so the user gets an explanation instead of an empty card.
        if state.get("recommended_actions"):
            return "hitl"
    return "final_response"
