from domains.common import Anomaly, ProductRef, TimeRange
from domains.customer_support.schemas import CustomerComplaint, CustomerSupportAnalysis
from domains.inventory.schemas import InventoryAnalysis, StockLevel
from domains.marketing.schemas import Campaign, CampaignMetrics, MarketingAnalysis
from domains.sales.schemas import ProductRevenue, SalesAnalysis, SalesMetrics

from schemas.actions import (
    ActionApprovalResponse,
    ActionExecutionResult,
    RecommendedAction,
)
from schemas.analysis import (
    CrossDomainCorrelation,
    DomainAnalysisData,
    DomainFinding,
    ReflectionResult,
    RootCauseAnalysis,
)
from schemas.outputs import OperationsReport
from schemas.query import Query

__all__ = [
    # actions
    "ActionApprovalResponse",
    "ActionExecutionResult",
    "RecommendedAction",
    # analysis
    "CrossDomainCorrelation",
    "DomainAnalysisData",
    "DomainFinding",
    "ReflectionResult",
    "RootCauseAnalysis",
    # common
    "Anomaly",
    "ProductRef",
    "TimeRange",
    # customer_support
    "CustomerComplaint",
    "CustomerSupportAnalysis",
    # inventory
    "InventoryAnalysis",
    "StockLevel",
    # marketing
    "Campaign",
    "CampaignMetrics",
    "MarketingAnalysis",
    # outputs
    "OperationsReport",
    # query
    "Query",
    # sales
    "ProductRevenue",
    "SalesAnalysis",
    "SalesMetrics",
]
