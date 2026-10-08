"""Shipping MCP server — owns carrier tracking data (read-only)."""

from mcp.server.mcpserver import MCPServer

from shopdesk.mcp_servers._common import load, serve

server = MCPServer(name="shipping", instructions="Read-only shipment tracking.")


@server.tool()
def track_shipment(tracking_id: str) -> dict:
    """Carrier, status, last scan and ETA for a tracking ID (format TRK-1234)."""
    s = load("shipments").get(tracking_id.strip().upper())
    if not s:
        return {"found": False, "tracking_id": tracking_id}
    return {"found": True, "tracking_id": tracking_id.upper(), **s}


if __name__ == "__main__":
    serve(server, default_port=8103)
