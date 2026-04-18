"""MCP client registry — connects to the MCP operations server and provides LangChain tools.

Lifecycle:
    initialize_mcp_registry()  — called once during FastAPI lifespan startup
    get_mcp_registry()         — returns the singleton (or None if disabled)
    close_mcp_registry()       — called during shutdown

Tool filtering:
    All tools live on one MCP server. The USE_MCP_TOOLS setting controls which
    domain tools are loaded into the registry. Each domain agent's YAML config
    further restricts which tools it may call.

Note:
    ``MultiServerMCPClient`` is the only client class in langchain-mcp-adapters;
    it works fine with a single server entry.
"""

from __future__ import annotations

import logging
from typing import Any

from domains.tool_registry import ALL_DOMAINS, KNOWN_TOOLS, TOOL_DOMAIN_MAP
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.settings import settings

logger = logging.getLogger(__name__)


def _parse_enabled_domains() -> set[str]:
    raw = settings.USE_MCP_TOOLS.strip().lower()
    if raw in ("none", ""):
        return set()
    if raw == "all":
        return set(ALL_DOMAINS)
    return {d.strip() for d in raw.split(",")}


def _wrap_with_retry(tool: StructuredTool) -> StructuredTool:
    """Wrap a StructuredTool's async invocation with tenacity retry."""
    original_coro = tool.coroutine
    if original_coro is None:
        return tool

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def _retrying(*args: Any, **kwargs: Any) -> Any:
        return await original_coro(*args, **kwargs)

    copy = tool.model_copy()
    object.__setattr__(copy, "coroutine", _retrying)
    return copy


class MCPClientRegistry:
    """Connects to the unified MCP server, caches tool manifests, exposes LangChain tools."""

    def __init__(self) -> None:
        self._client: MultiServerMCPClient | None = None
        self._tools: dict[str, StructuredTool] = {}
        self._enabled_domains: set[str] = set()
        self._live_tool_names: frozenset[str] = frozenset()

    @property
    def enabled_domains(self) -> set[str]:
        return self._enabled_domains

    @property
    def live_tool_names(self) -> frozenset[str]:
        """Tool names reported by the MCP server at startup."""
        return self._live_tool_names

    async def initialize(self) -> None:
        self._enabled_domains = _parse_enabled_domains()
        if not self._enabled_domains:
            logger.info("MCP tools disabled (USE_MCP_TOOLS=%s)", settings.USE_MCP_TOOLS)
            return

        server_config = {
            "operations": {
                "url": f"{settings.MCP_URL.rstrip('/')}/mcp",
                "transport": "streamable_http",
            }
        }

        logger.info("Connecting to MCP server: %s", settings.MCP_URL)
        self._client = MultiServerMCPClient(server_config)

        raw_tools = await self._client.get_tools()
        self._live_tool_names = frozenset(tool.name for tool in raw_tools)

        # Detect drift between the static KNOWN_TOOLS registry and what the
        # MCP server actually exposes.
        if self._live_tool_names != KNOWN_TOOLS:
            only_registry = KNOWN_TOOLS - self._live_tool_names
            only_server = self._live_tool_names - KNOWN_TOOLS
            logger.error(
                "Tool registry drift detected! "
                "In KNOWN_TOOLS but missing from MCP server: %s. "
                "On MCP server but missing from KNOWN_TOOLS: %s.",
                sorted(only_registry) or "none",
                sorted(only_server) or "none",
            )

        for tool in raw_tools:
            domain = TOOL_DOMAIN_MAP.get(tool.name)
            if domain and domain in self._enabled_domains:
                self._tools[tool.name] = _wrap_with_retry(tool)

        logger.info(
            "Loaded %d MCP tools (enabled domains: %s): %s",
            len(self._tools),
            sorted(self._enabled_domains),
            list(self._tools.keys()),
        )

    def get_tool(self, name: str) -> StructuredTool | None:
        return self._tools.get(name)

    async def close(self) -> None:
        if self._client:
            try:
                await self._client.close()
            except Exception:
                logger.warning("Error closing MCP client", exc_info=True)
            self._client = None
            self._tools.clear()
            logger.info("MCP client connection closed")


# ── Module-level singleton ──────────────────────────────────────────────

_registry: MCPClientRegistry | None = None


def get_mcp_registry() -> MCPClientRegistry | None:
    """Return the singleton registry, or None if not yet initialized."""
    return _registry


async def initialize_mcp_registry() -> MCPClientRegistry:
    global _registry
    # Clear cached agents so they pick up fresh MCP tool references.
    from agents.nodes import clear_agent_cache

    clear_agent_cache()
    _registry = MCPClientRegistry()
    await _registry.initialize()
    return _registry


async def close_mcp_registry() -> None:
    global _registry
    if _registry:
        await _registry.close()
        _registry = None
