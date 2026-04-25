"""Unified MCP server — registers all domain tools on a single FastMCP instance.

Each domain agent in the backend selectively accesses only its own tools
via the YAML config (tools whitelist). The MCP server itself exposes everything.
"""

import json
import logging
import sys
from datetime import datetime, timezone

from domains.customer_support.tools import (
    create_support_ticket,
    execute_create_support_ticket,
    get_customer_support_snapshot,
    get_tickets,
)
from domains.inventory.tools import execute_restock, get_inventory_snapshot, get_stockout_impact, restock
from domains.marketing.tools import (
    execute_pause_campaign,
    execute_resume_campaign,
    get_campaign_status,
    pause_campaign,
    resume_campaign,
)
from domains.memory.tools import preload_model, search_past_incidents
from domains.sales.tools import (
    compare_sales_periods,
    detect_revenue_anomalies,
    execute_run_discount,
    get_active_discounts,
    get_daily_sales_metrics,
    run_discount,
)
from fastmcp import FastMCP
from settings import get_settings


# ── Structured JSON logging ────────────────────────────────────────────
class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "mcp-operations",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(get_settings().LOG_LEVEL.upper())


_setup_logging()
logger = logging.getLogger("mcp-operations")

# ── FastMCP server ─────────────────────────────────────────────────────
mcp = FastMCP("operations")

# Sales tools
mcp.tool()(get_daily_sales_metrics)
mcp.tool()(compare_sales_periods)
mcp.tool()(detect_revenue_anomalies)
mcp.tool()(execute_run_discount)
mcp.tool()(get_active_discounts)
mcp.tool()(run_discount)

# Inventory tools
mcp.tool()(get_inventory_snapshot)
mcp.tool()(get_stockout_impact)
mcp.tool()(execute_restock)
mcp.tool()(restock)

# Marketing tools
mcp.tool()(get_campaign_status)
mcp.tool()(execute_pause_campaign)
mcp.tool()(execute_resume_campaign)
mcp.tool()(pause_campaign)
mcp.tool()(resume_campaign)

# Customer support tools
mcp.tool()(get_customer_support_snapshot)
mcp.tool()(get_tickets)
mcp.tool()(execute_create_support_ticket)
mcp.tool()(create_support_ticket)

# Memory tools
mcp.tool()(search_past_incidents)


if __name__ == "__main__":
    settings = get_settings()
    # Pre-load the embedding model so the first search_past_incidents call
    # doesn't block the event loop with a ~130MB download + model init.
    preload_model()
    logger.info("Starting operations MCP server on %s:%s", settings.HOST, settings.PORT)
    mcp.run(transport="streamable-http", host=settings.HOST, port=settings.PORT)
