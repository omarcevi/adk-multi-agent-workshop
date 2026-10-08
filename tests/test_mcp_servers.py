"""Tool servers: tool logic, stdio + HTTP transports, Cloud Run identity tokens, container contents."""

import ast
import asyncio
import base64
import json
import os
import socket
import threading
import time

import httpx
import uvicorn

from shopdesk.mcp_servers import inventory, orders, shipping

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_tool_logic():
    assert orders.get_order("ord-1001")["found"]
    assert not orders.get_order("ORD-9999")["found"]
    assert len(orders.list_customer_orders("C-42")["orders"]) == 2
    assert inventory.find_alternatives("LAMP-MINI")["alternatives"][0]["sku"] == "LAMP-ARC"
    assert shipping.track_shipment("TRK-7790")["status"] == "in_transit"


def test_stdio_toolset_lists_filtered_tools(monkeypatch):
    from shopdesk import config
    from shopdesk.tools import mcp_toolset

    monkeypatch.setitem(config.MCP_URLS, "inventory", "")
    ts = mcp_toolset("inventory", ["check_stock"])

    async def go():
        tools = await ts.get_tools()
        await ts.close()
        return [t.name for t in tools]

    assert asyncio.run(go()) == ["check_stock"]


def _fake_id_token(exp_in=3600):
    body = base64.urlsafe_b64encode(json.dumps({"exp": time.time() + exp_in}).encode()).decode().rstrip("=")
    return f"h.{body}.s"


def test_http_transport_sends_cloud_run_identity_token(monkeypatch):
    """Over HTTP every MCP request carries `Authorization: Bearer <identity token>`,
    the way Cloud Run expects. The token fetch itself is faked here."""
    from shopdesk import auth, config
    from shopdesk.tools import mcp_toolset

    seen = []

    class Recorder:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                seen.append(dict(scope["headers"]).get(b"authorization", b"").decode())
            await self.app(scope, receive, send)

    from mcp.server.transport_security import TransportSecuritySettings

    app = Recorder(shipping.server.streamable_http_app(
        stateless_http=True, host="0.0.0.0",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)))
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    for _ in range(50):
        try:
            httpx.get(f"http://127.0.0.1:{port}/", timeout=0.5); break
        except httpx.TransportError:
            time.sleep(0.1)
    seen.clear()  # ignore the readiness probe above

    token = _fake_id_token()
    fetched = []
    monkeypatch.setattr(auth._IdTokens, "_fetch", staticmethod(lambda aud: fetched.append(aud) or token))
    monkeypatch.setattr(auth, "_ID_TOKENS", auth._IdTokens())
    monkeypatch.setitem(config.MCP_URLS, "shipping", f"http://127.0.0.1:{port}/mcp")
    monkeypatch.setattr(config, "MCP_AUTH", "google")
    try:
        ts = mcp_toolset("shipping")

        async def go():
            tools = await ts.get_tools()
            res = await tools[0].run_async(args={"tracking_id": "TRK-7781"}, tool_context=None)
            await ts.close()
            return [t.name for t in tools], res

        names, res = asyncio.run(go())
        assert names == ["track_shipment"] and "delivered" in str(res)
        assert seen and all(h == f"Bearer {token}" for h in seen)
        assert fetched == [f"http://127.0.0.1:{port}"]  # audience = service URL; cached after first fetch
    finally:
        srv.should_exit = True; th.join(5)


def test_id_token_cache_refreshes_near_expiry(monkeypatch):
    from shopdesk import auth

    calls = []
    tokens = [_fake_id_token(100), _fake_id_token(3600)]  # first one is about to expire
    monkeypatch.setattr(auth._IdTokens, "_fetch", staticmethod(lambda aud: calls.append(aud) or tokens[len(calls) - 1]))
    cache = auth._IdTokens()
    assert cache.get("https://x.run.app") == tokens[0]
    assert cache.get("https://x.run.app") == tokens[1]  # < 5 min left -> refetched
    assert cache.get("https://x.run.app") == tokens[1]  # now cached
    assert len(calls) == 2


def test_container_has_everything_the_servers_import():
    """The Dockerfile copies only shopdesk/__init__.py, config.py, data/ and mcp_servers/.
    Make sure the servers import nothing else from shopdesk (and no ADK)."""
    allowed = {"shopdesk", "shopdesk.config", "shopdesk.mcp_servers", "shopdesk.mcp_servers._common"}
    files = [os.path.join(ROOT, "shopdesk", "config.py")] + [
        os.path.join(ROOT, "shopdesk", "mcp_servers", f)
        for f in os.listdir(os.path.join(ROOT, "shopdesk", "mcp_servers")) if f.endswith(".py")
    ]
    for path in files:
        for node in ast.walk(ast.parse(open(path).read())):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for m in mods:
                assert not m.startswith("google.adk"), f"{path} imports {m}"
                if m.startswith("shopdesk"):
                    assert m in allowed, f"{path} imports {m}, which the container doesn't copy"


def test_envfile_set_and_get(tmp_path, monkeypatch):
    from scripts import envfile

    monkeypatch.setattr(envfile, "ENV", tmp_path / ".env")
    envfile.set_value("A", "1")
    envfile.set_value("B", "x=y")
    envfile.set_value("A", "2")
    assert envfile.get_value("A") == "2" and envfile.get_value("B") == "x=y"
    assert (tmp_path / ".env").read_text().count("A=") == 1
