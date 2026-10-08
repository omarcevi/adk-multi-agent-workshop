"""make check-mcp — find your tool servers, then knock on each one twice.

1. Looks up the three Cloud Run services you deployed (shopdesk-<name>-mcp) and
   saves their URLs into .env, so the agents know where the tools live.
2. Calls each server without a Google identity token: Cloud Run rejects it
   before our code runs. Then with yours (you own the project, so you hold
   roles/run.invoker): the MCP server answers with its tool list.
"""

import asyncio
import subprocess

import httpx

from scripts.envfile import set_value
from shopdesk import config
from shopdesk.tools import mcp_toolset

SERVERS = ["orders", "inventory", "shipping"]


def discover_urls() -> None:
    for name in SERVERS:
        out = subprocess.run(
            ["gcloud", "run", "services", "describe", f"shopdesk-{name}-mcp",
             "--region", config.REGION, "--format=value(status.url)"],
            capture_output=True, text=True,
        )
        url = out.stdout.strip()
        if url:
            config.MCP_URLS[name] = f"{url}/mcp"
            set_value(f"{name.upper()}_MCP_URL", config.MCP_URLS[name])


async def main():
    discover_urls()
    for name in SERVERS:
        url = config.MCP_URLS[name]
        if not url:
            print(f"{name:<10} not found: is shopdesk-{name}-mcp deployed in {config.REGION}?")
            continue
        anon = httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=20)
        ts = mcp_toolset(name)
        tools = await ts.get_tools()
        await ts.close()
        print(f"{name:<10} anonymous: HTTP {anon.status_code} {anon.reason_phrase:<10} "
              f"| with your identity: {', '.join(t.name for t in tools)}")
    print("\nURLs saved to .env. Restart `adk web` if it is running, so agents pick them up.")


if __name__ == "__main__":
    asyncio.run(main())
