"""Inventory MCP server — owns stock levels and product alternatives (read-only)."""

from mcp.server.mcpserver import MCPServer

from shopdesk.mcp_servers._common import load, serve

server = MCPServer(name="inventory", instructions="Read-only stock and catalog lookups.")


@server.tool()
def check_stock(sku: str) -> dict:
    """Current stock for a SKU (e.g. KTL-STEEL), its warehouse and restock ETA if any."""
    item = load("inventory").get(sku.strip().upper())
    if not item:
        return {"found": False, "sku": sku}
    return {"found": True, "sku": sku.upper(), **item}


@server.tool()
def find_alternatives(sku: str) -> dict:
    """In-stock replacement products for a SKU, for exchanges when the original is unavailable."""
    inv = load("inventory")
    item = inv.get(sku.strip().upper())
    if not item:
        return {"found": False, "sku": sku}
    alts = [
        {"sku": a, "name": inv[a]["name"], "stock": inv[a]["stock"]}
        for a in item.get("alternatives", [])
        if inv.get(a, {}).get("stock", 0) > 0
    ]
    return {"found": True, "sku": sku.upper(), "alternatives": alts}


if __name__ == "__main__":
    serve(server, default_port=8102)
