"""make check-mcp — knock on each tool server twice: without and with your identity.

Without a Google identity token, Cloud Run rejects the call before our code
runs. With yours (you own the project, so you hold roles/run.invoker) the MCP
server answers with its tool list.
"""

import asyncio

import httpx

from shopdesk import config
from shopdesk.tools import mcp_toolset

SERVERS = ["orders", "inventory", "shipping"]


async def main():
    for name in SERVERS:
        url = config.MCP_URLS[name]
        if not url:
            print(f"{name:<10} no URL in .env yet -> make deploy-mcp")
            continue
        anon = httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=20)
        ts = mcp_toolset(name, tool_filter=None)
        tools = await ts.get_tools()
        await ts.close()
        print(f"{name:<10} anonymous: HTTP {anon.status_code} {anon.reason_phrase:<10} "
              f"| with your identity: {', '.join(t.name for t in tools)}")


if __name__ == "__main__":
    asyncio.run(main())
