from typing import Annotated, Literal

from domains.common import Severity
from domains.customer_support.schemas import CustomerSupportAnalysis
from domains.inventory.schemas import InventoryAnalysis
from domains.marketing.schemas import MarketingAnalysis
from domains.sales.schemas import SalesAnalysis
from pydantic import BaseModel, Field, field_validator

from core.enums import AgentDomain

DomainAnalysisData = Annotated[
    SalesAnalysis | InventoryAnalysis | MarketingAnalysis | CustomerSupportAnalysis,
    Field(discriminator="kind"),
]


class CrossDomainCorrelation(BaseModel):
    description: str = Field(..., description="Human-readable description of the correlation")
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting evidence for this correlation",
    )


class DomainFinding(BaseModel):
    domain: AgentDomain = Field(..., description="Domain this finding belongs to")
    severity: Severity = Field(..., description="Severity of the issues found")
    data: DomainAnalysisData = Field(..., description="Detailed domain analysis output")


class RootCauseAnalysis(BaseModel):
    is_incomplete: bool = Field(..., description="Whether analysis is incomplete due to insufficient data")
    primary_cause: str | list[str] = Field(
        ...,
        description="The most likely root cause(s) of the issue, based on the analysis",
    )
    contributing_factors: list[str] = Field(
        default_factory=list,
        description="Additional factors that contributed to the issue",
    )
    correlations: list[CrossDomainCorrelation] = Field(
        default_factory=list,
        description=(
            "Cross-domain signal correlations identified."
            " Each item must be an object with 'description' and 'evidence' keys."
        ),
    )

    @field_validator("correlations", mode="before")
    @classmethod
    def _coerce_correlations(cls, v: list) -> list:
        """LLMs sometimes return plain strings instead of correlation objects."""
        coerced = []
        for item in v:
            if isinstance(item, str):
                coerced.append({"description": item, "evidence": []})
            else:
                coerced.append(item)
        return coerced

    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence supporting the root cause conclusion",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score for this root cause (0-1)",
    )


class ReflectionResult(BaseModel):
    is_complete: bool = Field(..., description="Whether the analysis is complete and ready to present")
    needs_more_data: bool = Field(..., description="Whether additional domain analysis is required")
    missing_domains: list[AgentDomain] = Field(
        default_factory=list,
        description="Domains that should be added in the next iteration",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Final confidence score after evaluation",
    )
    action_required: bool = Field(..., description="Whether an action should be triggered")
    issues: dict[str, str] = Field(
        default_factory=dict,
        description="Breakdown of issues: coverage, evidence, consistency",
    )


class RouterIntent(BaseModel):
    """Output schema for domain routing."""

    domains_to_run: list[AgentDomain] = Field(
        default_factory=list,
        description="Relevant business domains. Empty if out-of-scope, meta, or past-incident lookup.",
    )

    intent_type: Literal["broad", "targeted", "out_of_scope"] = Field(
        ...,
        description="High-level query intent classification.",
    )

    is_meta: bool = Field(
        ...,
        description="True if query is about the conversation itself.",
    )

    action_requested: bool = Field(
        default=False,
        description=(
            "True if the user is explicitly requesting that an action be taken"
            " (e.g. restock, run a discount, pause a campaign, open a ticket)."
        ),
    )
