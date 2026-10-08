"""MODULE 1 — how an agent reaches a tool server.

The agent knows only a URL. It doesn't import the server's code, share its
database, or know how it is deployed. Swap the server's implementation and the
agent never notices: that is the "decoupled" part.

Look at:
  * mcp_toolset()        URL in -> ADK toolset out
  * DEFAULT_TOOL_FILTERS least privilege: each agent sees only the tools it needs
"""

from __future__ import annotations

import sys

from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
    create_mcp_http_client,
)
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import StdioServerParameters

from shopdesk import config
from shopdesk.auth import CloudRunAuth

# Least privilege: the server may expose more tools than an agent is allowed to use.
# TRY THIS (Module 1): remove "check_stock" below, restart adk web, and ask
# "Is the oak chair in stock?" — the agent has lost that ability.
DEFAULT_TOOL_FILTERS: dict[str, list[str]] = {
    "orders": ["get_order", "list_customer_orders"],
    "inventory": ["check_stock", "find_alternatives"],
    "shipping": ["track_shipment"],
    "policy": ["search_policy"],  # bonus_rag/
}


def _client_with_cloud_run_auth(headers=None, timeout=None, auth=None):
    """Every request to Cloud Run carries a fresh Google identity token."""
    return create_mcp_http_client(headers=headers, timeout=timeout, auth=auth or CloudRunAuth())


def mcp_toolset(server: str, tool_filter: list[str] | None = None) -> McpToolset:
    if server not in config.MCP_URLS:
        raise ValueError(f"unknown MCP server {server!r}")
    url = config.MCP_URLS[server]

    if url:  # the normal path: a deployed Cloud Run service
        params = StreamableHTTPConnectionParams(
            url=url,
            timeout=30,
            httpx_client_factory=(
                create_mcp_http_client if config.MCP_AUTH == "none" else _client_with_cloud_run_auth
            ),
        )
    else:  # no URL yet (offline tests): run the same server as a local subprocess
        params = StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", f"shopdesk.mcp_servers.{server}", "--transport", "stdio"],
            ),
            timeout=30,
        )
    return McpToolset(
        connection_params=params,
        tool_filter=tool_filter or DEFAULT_TOOL_FILTERS[server],
    )
