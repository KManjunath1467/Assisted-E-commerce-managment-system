from typing import Annotated, Literal, TypedDict

from domains.common import TimeRange
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from core.enums import AgentDomain
from schemas.actions import RecommendedAction
from schemas.analysis import DomainFinding, ReflectionResult, RootCauseAnalysis
from schemas.outputs import OperationsReport


def _merge_domain_findings(existing: list[DomainFinding], new: list[DomainFinding] | None) -> list[DomainFinding]:
    """Replace findings for domains present in `new`; keep others unchanged.

    Returning None from a node signals an explicit reset (e.g. router at the
    start of each turn). Returning [] is a no-op so domain nodes that found
    nothing don't wipe out other domains' findings during retries.
    """
    if new is None:
        return []
    by_domain = {f.domain: f for f in existing}
    for f in new:
        by_domain[f.domain] = f
    return list(by_domain.values())


class GraphState(TypedDict):
    query: str
    thread_id: str | None
    time_range: TimeRange | None
    incident_id: str | None
    domains_to_run: list[AgentDomain]
    domain_findings: Annotated[list[DomainFinding], _merge_domain_findings]
    root_cause: RootCauseAnalysis | None
    reflection: ReflectionResult | None
    recommended_actions: list[RecommendedAction]
    report: OperationsReport | None
    requires_hitl: bool
    action_requested: bool
    intent_type: Literal["broad", "targeted", "out_of_scope"]
    is_meta: bool
    requires_deep_analysis: bool
    retry_count: int
    conversation_history: Annotated[list[BaseMessage], add_messages]
