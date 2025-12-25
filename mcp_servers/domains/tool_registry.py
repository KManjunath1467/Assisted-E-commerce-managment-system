"""Tool registry — single source of truth for tool metadata.

The backend imports this to know which tools exist, which domain they belong to,
and what schema each tool returns.
"""

from __future__ import annotations

from domains.common import Anomaly
from domains.customer_support.schemas import CustomerSupportAnalysis
from domains.inventory.schemas import InventoryAnalysis
from domains.marketing.schemas import MarketingAnalysis
from domains.memory.schemas import PastIncidentSearchResult
from domains.sales.schemas import SalesAnalysis

# Tool name → domain the tool belongs to.
TOOL_DOMAIN_MAP: dict[str, str] = {
    "get_daily_sales_metrics": "sales",
    "compare_sales_periods": "sales",
    "detect_revenue_anomalies": "sales",
    "get_inventory_snapshot": "inventory",
    "get_stockout_impact": "inventory",
    "get_campaign_status": "marketing",
    "get_customer_support_snapshot": "customer_support",
    "search_past_incidents": "memory",
}

# All valid tool names.
KNOWN_TOOLS: frozenset[str] = frozenset(TOOL_DOMAIN_MAP)

# All domain names.
ALL_DOMAINS: frozenset[str] = frozenset(TOOL_DOMAIN_MAP.values())

# Tool name → Pydantic model for deserialising MCP responses.
# None means the tool returns list[Anomaly] (detect_revenue_anomalies).
TOOL_OUTPUT_SCHEMA: dict[str, type | None] = {
    "get_daily_sales_metrics": SalesAnalysis,
    "compare_sales_periods": SalesAnalysis,
    "detect_revenue_anomalies": None,
    "get_inventory_snapshot": InventoryAnalysis,
    "get_stockout_impact": InventoryAnalysis,
    "get_campaign_status": MarketingAnalysis,
    "get_customer_support_snapshot": CustomerSupportAnalysis,
    "search_past_incidents": PastIncidentSearchResult,
}
