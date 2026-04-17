"""LangGraph graph construction for the e-commerce operations assistant."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.nodes import (
    aggregator_node,
    cx_node,
    final_response_node,
    hitl_node,
    inventory_node,
    marketing_node,
    orchestrator_node,
    reflector_node,
    router_node,
    sales_node,
)
from agents.routing import route_after_aggregator, route_after_reflector
from agents.state import GraphState
from core.enums import AgentDomain


def build_graph(checkpointer=None):
    """Build and compile the operations assistant graph.

    Args:
        checkpointer: LangGraph checkpointer for state persistence.
                      Defaults to an in-memory saver so that ``interrupt()``
                      always has a backend to write to (required by LangGraph).
                      Pass an ``AsyncPostgresSaver`` in production.
    """
    effective_checkpointer = checkpointer or MemorySaver()

    g = StateGraph(GraphState)

    g.add_node("router", router_node)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node(AgentDomain.SALES.value, sales_node)
    g.add_node(AgentDomain.INVENTORY.value, inventory_node)
    g.add_node(AgentDomain.MARKETING.value, marketing_node)
    g.add_node(AgentDomain.CUSTOMER_SUPPORT.value, cx_node)
    g.add_node("aggregator", aggregator_node)
    g.add_node("reflector", reflector_node)
    g.add_node("hitl", hitl_node)
    g.add_node("final_response", final_response_node)

    g.add_edge(START, "router")
    g.add_edge("router", "orchestrator")

    # Fan-in: all domain nodes → aggregator.
    # Fan-out routing is handled by orchestrator_node returning
    # Command(goto=[Send(...)]).
    for domain in AgentDomain:
        g.add_edge(domain.value, "aggregator")

    g.add_conditional_edges(
        "aggregator",
        route_after_aggregator,
        {
            "reflector": "reflector",
            "final_response": "final_response",
        },
    )

    # Reflector routing
    g.add_conditional_edges(
        "reflector",
        route_after_reflector,
        {
            "orchestrator": "orchestrator",
            "hitl": "hitl",
            "final_response": "final_response",
        },
    )

    g.add_edge("hitl", "final_response")
    g.add_edge("final_response", END)

    return g.compile(checkpointer=effective_checkpointer)
