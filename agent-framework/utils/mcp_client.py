"""FastMCP StreamableHTTP client setup for connecting to the PerfPilot Hub gateway.

Each agent uses this module to reach MCP tools (BlazeMeter, Datadog, JMeter,
PerfAnalysis, PerfReport, Confluence, PerfMemory) through the `gateway-mcp`
server. The script-agent additionally reaches the Microsoft Playwright MCP
container via a separate URL configured in `.env` / `config.yaml`.

The agent's `allowed_namespaces` list (from its `config.yaml`) drives namespace
filtering: only tools whose names start with one of the allowed namespace
prefixes are exposed to the LLM. This is a security and clarity boundary, not
a hard protocol restriction. See V2 doc Section 13.

Status:
    F3.2 (this commit) - URL resolution, namespace filtering helper, public
        API surface. The real FastMCP client construction raises
        `NotImplementedError` until F3.7.
    F3.7 - real FastMCP `StreamableHttpClient` wiring alongside the orchestrator.
    F3.13 - auth header propagation and OpenTelemetry span hooks lit up.

Heavy imports (`fastmcp`) are deferred into the function that needs them so
this module can be imported in environments without FastMCP installed
(structural smoke test, IDE indexing, etc.).
"""

import logging
import os
from dataclasses import dataclass
from typing import Iterable

log = logging.getLogger(__name__)

DEFAULT_GATEWAY_URL = "http://localhost:8000/mcp"
DEFAULT_PLAYWRIGHT_URL = "http://localhost:8003/mcp"


@dataclass(frozen=True)
class McpClientConfig:
    """Connection configuration for a per-agent MCP client.

    Attributes:
        gateway_url: HTTP endpoint of the PerfPilot Hub gateway.
        allowed_namespaces: Tuple of namespace prefixes (for example,
            `("blazemeter_", "datadog_")`) that this client may invoke. The
            single-element tuple `("*",)` allows everything (orchestrator
            only).
    """

    gateway_url: str
    allowed_namespaces: tuple[str, ...]


def resolve_gateway_url() -> str:
    """Resolve the gateway URL.

    Priority:
        1. `GATEWAY_MCP_URL` environment variable
        2. `DEFAULT_GATEWAY_URL` constant (loopback for local dev)
    """
    return os.environ.get("GATEWAY_MCP_URL", DEFAULT_GATEWAY_URL)


def resolve_playwright_url() -> str:
    """Resolve the Microsoft Playwright MCP URL.

    Used only by the script-agent. Other agents must not call this.
    """
    return os.environ.get("PLAYWRIGHT_MCP_URL", DEFAULT_PLAYWRIGHT_URL)


def build_client_config(allowed_namespaces: Iterable[str]) -> McpClientConfig:
    """Construct an `McpClientConfig` from an agent's `allowed_namespaces`.

    Args:
        allowed_namespaces: Iterable of namespace prefixes from the agent's
            `config.yaml`. Duplicates are deduplicated and ordering is made
            deterministic for reproducibility.

    Returns:
        Frozen `McpClientConfig` ready to pass to `create_mcp_client()`.
    """
    namespaces = tuple(sorted({n.strip() for n in allowed_namespaces if n and n.strip()}))
    if not namespaces:
        log.warning(
            "build_client_config received an empty allowed_namespaces list; "
            "the resulting client will expose no tools to the LLM"
        )
    return McpClientConfig(
        gateway_url=resolve_gateway_url(),
        allowed_namespaces=namespaces,
    )


def filter_tools(
    tool_catalog: list,
    allowed_namespaces: tuple[str, ...],
) -> list:
    """Filter the gateway's full tool catalog to only the allowed namespaces.

    Tool names follow the convention `<namespace>_<tool_name>`, for example
    `blazemeter_run_test` or `datadog_get_metrics`. A namespace prefix of
    `"*"` allows every tool (orchestrator-only convention).

    Args:
        tool_catalog: Full list of tools returned by the FastMCP client. Each
            entry may be either an object with a `.name` attribute or a dict
            containing a `"name"` key; both shapes are accepted.
        allowed_namespaces: Tuple of allowed prefixes; `("*",)` for "all".

    Returns:
        Filtered list, preserving original tool order.
    """
    if not allowed_namespaces:
        return []
    if "*" in allowed_namespaces:
        return list(tool_catalog)

    filtered: list = []
    for tool in tool_catalog:
        tool_name = None
        if hasattr(tool, "name"):
            tool_name = getattr(tool, "name")
        elif isinstance(tool, dict):
            tool_name = tool.get("name")
        if not tool_name:
            continue
        if any(tool_name.startswith(ns) for ns in allowed_namespaces):
            filtered.append(tool)
    return filtered


async def create_mcp_client(config: McpClientConfig):
    """Create a FastMCP client connected to the gateway.

    F3.2 status: structural skeleton; raises `NotImplementedError`. Real
    `StreamableHttpClient` wiring lands in F3.7 (orchestrator) and F3.8
    (execution-agent vertical slice).

    Args:
        config: `McpClientConfig` built by `build_client_config()`.

    Returns:
        FastMCP client instance once F3.7 lands.

    Raises:
        NotImplementedError: Until F3.7.
    """
    raise NotImplementedError(
        "FastMCP StreamableHttpClient wiring lights up in F3.7 (orchestrator) "
        "and F3.8 (execution-agent vertical slice). "
        f"Configured for gateway_url={config.gateway_url}, "
        f"allowed_namespaces={config.allowed_namespaces}."
    )
