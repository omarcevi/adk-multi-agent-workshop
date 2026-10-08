"""Shared plumbing for the MCP tool servers.

Each server is its own small microservice: own Cloud Run service, own data,
own URL. The agent side never imports this code; it only speaks MCP.

Security lives in the platform, not in this file: the services are deployed
with unauthenticated access OFF, so Cloud Run rejects any request without a
Google identity token from someone holding `roles/run.invoker`.
"""

from __future__ import annotations

import argparse
import json
import os
from functools import lru_cache

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from shopdesk.config import DATA_DIR


@lru_cache
def load(name: str) -> dict:
    """Read-only mock data. In real life: your orders DB, warehouse system, carrier API."""
    with open(DATA_DIR / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def serve(server: MCPServer, default_port: int) -> None:
    """Run a server over Streamable HTTP (Cloud Run) or stdio (offline tests)."""
    parser = argparse.ArgumentParser(description=f"{server.name} MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="http")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", default_port)))
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run("stdio")
        return

    import uvicorn

    app = server.streamable_http_app(
        stateless_http=True,  # every request stands alone: scales to zero, any instance can answer
        host=args.host,
        # Cloud Run's front end already authenticates callers and owns the host name.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    print(f"[{server.name}] MCP over HTTP on http://{args.host}:{args.port}/mcp", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
