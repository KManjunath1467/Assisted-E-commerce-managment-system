"""Declarative agent factory — loads per-agent YAML configs and builds agents
via langchain.agents.create_agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

import yaml
from domains.common import Anomaly
from domains.tool_registry import TOOL_OUTPUT_SCHEMA
from langchain.agents import create_agent as _lc_create_agent
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI

from core.settings import settings
from schemas.analysis import (
    ReflectionResult,
    RootCauseAnalysis,
    RouterIntent,
)

logger = logging.getLogger(__name__)

CONFIGS_DIR = Path(__file__).parent / "configs"

SCHEMA_REGISTRY: dict[str, type] = {
    "RootCauseAnalysis": RootCauseAnalysis,
    "ReflectionResult": ReflectionResult,
    "RouterIntent": RouterIntent,
}


def _normalize_mcp_result(tool_name: str, result: Any) -> Any:
    """Convert MCP content-block responses into backend Pydantic models.

    MCP tools return ``([content_blocks], {"structured_content": {...}})``
    from the coroutine.  Inline tools return Pydantic model instances directly.
    This function detects the MCP tuple format and deserializes through the
    backend schema so domain builders see the same typed objects regardless of
    source.
    """
    # MCP coroutine returns a tuple (content_blocks, structured_dict).
    if isinstance(result, tuple) and len(result) == 2:
        content_blocks, extra = result
        # Prefer the structured_content dict (already parsed).
        if isinstance(extra, dict) and "structured_content" in extra:
            parsed = extra["structured_content"]
        elif isinstance(content_blocks, list) and content_blocks:
            first = content_blocks[0]
            if isinstance(first, dict) and first.get("type") == "text":
                try:
                    parsed = json.loads(first["text"])
                except (json.JSONDecodeError, TypeError):
                    return result
            else:
                return result
        else:
            return result

        schema = TOOL_OUTPUT_SCHEMA.get(tool_name)
        if schema is not None:
            return schema.model_validate(parsed)
        # detect_revenue_anomalies → list[Anomaly]; MCP may wrap as {"result": [...]}.
        if isinstance(parsed, dict) and "result" in parsed:
            parsed = parsed["result"]
        if isinstance(parsed, list):
            return [Anomaly.model_validate(item) for item in parsed]
        return parsed

    return result


# ---------------------------------------------------------------------------
# Capturing tool wrapper — preserves typed Python results before ToolNode
# converts them to strings for ToolMessage.content.
# A fresh list + fresh wrapper set is created per Agent.run() call so
# concurrent invocations never share state.
# ---------------------------------------------------------------------------


def _make_capturing_tool(tool: Any, store: list) -> Any:
    """Return a StructuredTool copy whose coroutine captures the typed result
    into *store* before returning a JSON-serialisable dict so that ToolNode's
    ``json.dumps`` succeeds (instead of falling back to ``str()``)."""
    original_coro = tool.coroutine

    async def _capturing(*args: Any, **kwargs: Any) -> Any:
        result = await original_coro(*args, **kwargs)
        # Normalise MCP content-block responses into backend Pydantic models.
        result = _normalize_mcp_result(tool.name, result)
        store.append((tool.name, result))
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        if isinstance(result, list) and result and hasattr(result[0], "model_dump"):
            return [item.model_dump(mode="json") for item in result]
        return result

    copy = tool.model_copy()
    # StructuredTool stores the async callable in its `coroutine` field.
    object.__setattr__(copy, "coroutine", _capturing)
    # MCP tools use response_format='content_and_artifact' which makes ToolNode
    # expect a (content, artifact) tuple.  Since our wrapper already normalises
    # and captures results, reset to plain 'content' so ToolNode accepts a dict.
    if getattr(copy, "response_format", None) == "content_and_artifact":
        object.__setattr__(copy, "response_format", "content")
    return copy


@lru_cache(maxsize=1)
def _get_llm() -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_endpoint=settings.DIAL_ENDPOINT,
        api_key=settings.DIAL_API_KEY,
        api_version=settings.DIAL_API_VERSION,
        azure_deployment=settings.DIAL_DEPLOYMENT,
        temperature=0.0,
    )


@dataclass
class AgentConfig:
    name: str
    system_prompt: str
    user_prompt_template: str
    tools: list[str] = field(default_factory=list)
    max_iterations: int = 5
    structured_output: str | None = None


class Agent:
    """A configured agent loaded from a YAML declaration.

    Tool-calling agents use langchain.agents.create_agent — the LLM has
    complete discretion over which whitelisted tools to call, how many
    times to call them, and whether to call any at all.

    Structured-output agents (no tools) call llm.with_structured_output directly.

    Plain-text agents (no tools, no schema) invoke the LLM once for free-form text.
    """

    def __init__(self, config: AgentConfig, resolved_tools: list) -> None:
        self._config = config
        self._tools = resolved_tools
        self._structured_schema = SCHEMA_REGISTRY[config.structured_output] if config.structured_output else None

    def __repr__(self) -> str:
        return (
            f"Agent(name={self._config.name!r}, "
            f"tools={[t.name for t in self._tools]}, "
            f"structured_output={self._config.structured_output!r})"
        )

    async def run(self, **kwargs: Any) -> tuple[list[BaseMessage], list[tuple[str, Any]]]:
        """Execute the agent.

        Template variables in user_prompt_template are filled with **kwargs via
        string.Template.safe_substitute, so arbitrary values (JSON, user queries,
        database content) cannot break the template expansion.

        Returns:
            messages     : full conversation message list
            tool_results : list of (tool_name, result) pairs.
                           Structured-output agents return [("__structured__", obj)].
                           Plain-text agents return [("__text__", content_str)].
        """
        user_content = Template(self._config.user_prompt_template).safe_substitute(**kwargs)
        messages: list[BaseMessage] = [
            SystemMessage(content=self._config.system_prompt),
            HumanMessage(content=user_content),
        ]

        # Structured output only (no tools) — single LLM call.
        if self._structured_schema is not None and not self._tools:
            result = (
                await _get_llm()
                .with_structured_output(self._structured_schema, method="function_calling")
                .ainvoke(messages)
            )
            return messages, [("__structured__", result)]

        # Tools + structured output — run tool loop first, then a final
        # structured-output call that sees the full conversation (including
        # tool results).  The agent decides which tools to call (if any).
        if self._tools and self._structured_schema is not None:
            captured: list[tuple[str, Any]] = []
            fresh_tools = [_make_capturing_tool(t, captured) for t in self._tools]
            agent = _lc_create_agent(
                _get_llm(),
                tools=fresh_tools,
                system_prompt=self._config.system_prompt,
            )
            output = await agent.ainvoke(
                {"messages": [HumanMessage(content=user_content)]},
                {"recursion_limit": self._config.max_iterations * 2 + 1},
            )
            # Second pass: structured-output call with the full conversation.
            result = (
                await _get_llm()
                .with_structured_output(self._structured_schema, method="function_calling")
                .ainvoke(output["messages"])
            )
            captured.append(("__structured__", result))
            return output["messages"], captured

        # Tool-calling via langchain.agents.create_agent — the agent decides
        # which tools to call, how many times, or whether to call any at all.
        # A fresh agent + capturing wrappers are created per call so concurrent
        # invocations never share capture state.
        if self._tools:
            captured: list[tuple[str, Any]] = []
            fresh_tools = [_make_capturing_tool(t, captured) for t in self._tools]
            agent = _lc_create_agent(
                _get_llm(),
                tools=fresh_tools,
                system_prompt=self._config.system_prompt,
            )
            output = await agent.ainvoke(
                {"messages": [HumanMessage(content=user_content)]},
                {"recursion_limit": self._config.max_iterations * 2 + 1},
            )
            return output["messages"], captured

        # Plain LLM call — no tools, no structured schema (e.g. final_response).
        response = await _get_llm().ainvoke(messages)
        return messages + [response], [("__text__", response.content)]


def create_agent(name: str) -> Agent:
    """Load agent config from configs/{name}.yml and return a ready Agent.

    Raises FileNotFoundError if the config file is missing.
    Raises ValueError if any listed tool name is unknown.
    Raises RuntimeError if MCP registry is not initialised for tool-using agents.
    """
    config_path = CONFIGS_DIR / f"{name}.yml"
    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    config = AgentConfig(
        name=raw["name"],
        system_prompt=raw["system_prompt"],
        user_prompt_template=raw["user_prompt_template"],
        tools=raw.get("tools") or [],
        max_iterations=raw.get("max_iterations", 5),
        structured_output=raw.get("structured_output"),
    )

    unknown = [t for t in config.tools if t not in _get_live_tool_names()]
    if unknown:
        raise ValueError(f"Agent '{name}' references unknown tools: {unknown}")

    resolved_tools = [_resolve_tool(t) for t in config.tools]
    return Agent(config, resolved_tools)


def _get_live_tool_names() -> frozenset[str]:
    """Return the live tool names from the MCP registry, falling back to the static registry."""
    from agents.mcp_registry import get_mcp_registry

    registry = get_mcp_registry()
    if registry is not None and registry.live_tool_names:
        return registry.live_tool_names
    from domains.tool_registry import KNOWN_TOOLS

    return KNOWN_TOOLS


def _resolve_tool(tool_name: str) -> Any:
    """Resolve a tool by name from the MCP registry.

    Raises RuntimeError if the MCP registry is not initialised or does not
    contain the requested tool.
    """
    from agents.mcp_registry import get_mcp_registry

    registry = get_mcp_registry()
    if registry is None:
        raise RuntimeError(
            f"Cannot resolve tool '{tool_name}': MCP registry not initialised. "
            "Ensure initialize_mcp_registry() has been called at startup."
        )
    tool = registry.get_tool(tool_name)
    if tool is None:
        raise RuntimeError(
            f"Tool '{tool_name}' not found in MCP registry. Available tools: {list(registry._tools.keys())}"
        )
    return tool
