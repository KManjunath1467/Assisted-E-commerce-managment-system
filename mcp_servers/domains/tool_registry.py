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
    "execute_run_discount": "sales",
    "get_active_discounts": "sales",
    "run_discount": "sales",
    "get_inventory_snapshot": "inventory",
    "get_stockout_impact": "inventory",
    "execute_restock": "inventory",
    "restock": "inventory",
    "get_campaign_status": "marketing",
    "execute_pause_campaign": "marketing",
    "execute_resume_campaign": "marketing",
    "pause_campaign": "marketing",
    "resume_campaign": "marketing",
    "get_customer_support_snapshot": "customer_support",
    "get_tickets": "customer_support",
    "execute_create_support_ticket": "customer_support",
    "create_support_ticket": "customer_support",
    "search_past_incidents": "memory",
}

# Write (action-request) tools — used to detect and partition tool results.
WRITE_ACTION_TOOLS: frozenset[str] = frozenset({
    "restock",
    "run_discount",
    "pause_campaign",
    "resume_campaign",
    "create_support_ticket",
})

# All valid tool names.
KNOWN_TOOLS: frozenset[str] = frozenset(TOOL_DOMAIN_MAP)

# All domain names.
ALL_DOMAINS: frozenset[str] = frozenset(TOOL_DOMAIN_MAP.values())

# Tool name → Pydantic model for deserialising MCP responses.
# None means the tool returns a plain dict (write tools and detect_revenue_anomalies).
TOOL_OUTPUT_SCHEMA: dict[str, type | None] = {
    "get_daily_sales_metrics": SalesAnalysis,
    "compare_sales_periods": SalesAnalysis,
    "detect_revenue_anomalies": None,
    "execute_run_discount": None,
    "get_active_discounts": None,
    "run_discount": None,
    "get_inventory_snapshot": InventoryAnalysis,
    "get_stockout_impact": InventoryAnalysis,
    "execute_restock": None,
    "restock": None,
    "get_campaign_status": MarketingAnalysis,
    "execute_pause_campaign": None,
    "execute_resume_campaign": None,
    "pause_campaign": None,
    "resume_campaign": None,
    "get_customer_support_snapshot": CustomerSupportAnalysis,
    "get_tickets": None,
    "execute_create_support_ticket": None,
    "create_support_ticket": None,
    "search_past_incidents": PastIncidentSearchResult,
}
