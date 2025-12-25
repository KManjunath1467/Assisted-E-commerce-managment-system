"""Unified MCP server — registers all domain tools on a single FastMCP instance.

Each domain agent in the backend selectively accesses only its own tools
via the YAML config (tools whitelist). The MCP server itself exposes everything.
"""

import json
import logging
import sys
from datetime import datetime, timezone

from domains.customer_support.tools import get_customer_support_snapshot
from domains.inventory.tools import get_inventory_snapshot, get_stockout_impact
from domains.marketing.tools import get_campaign_status
from domains.memory.tools import search_past_incidents
from domains.sales.tools import (
    compare_sales_periods,
    detect_revenue_anomalies,
    get_daily_sales_metrics,
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

# Inventory tools
mcp.tool()(get_inventory_snapshot)
mcp.tool()(get_stockout_impact)

# Marketing tools
mcp.tool()(get_campaign_status)

# Customer support tools
mcp.tool()(get_customer_support_snapshot)

# Memory tools
mcp.tool()(search_past_incidents)


if __name__ == "__main__":
    settings = get_settings()
    logger.info("Starting operations MCP server on %s:%s", settings.HOST, settings.PORT)
    mcp.run(transport="streamable-http", host=settings.HOST, port=settings.PORT)
