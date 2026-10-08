"""Orders MCP server — owns order and customer records (read-only)."""

from mcp.server.mcpserver import MCPServer

from shopdesk.mcp_servers._common import load, serve

server = MCPServer(
    name="orders",
    instructions="Read-only access to customer orders. Never invent order IDs.",
)


@server.tool()
def get_order(order_id: str) -> dict:
    """Look up one order by ID (format ORD-1234): status, items, total, tracking ID, notes."""
    order = load("orders").get(order_id.strip().upper())
    if not order:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id.upper(), **order}


@server.tool()
def list_customer_orders(customer_id: str) -> dict:
    """List order IDs and statuses for a customer ID (format C-12)."""
    cid = customer_id.strip().upper()
    orders = [
        {"order_id": oid, "status": o["status"], "placed_at": o["placed_at"], "total": o["total"]}
        for oid, o in load("orders").items()
        if o["customer_id"] == cid
    ]
    customer = load("customers").get(cid)
    return {"customer_id": cid, "customer": customer, "orders": orders}


if __name__ == "__main__":
    serve(server, default_port=8101)
