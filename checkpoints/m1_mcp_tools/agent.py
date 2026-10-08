"""CHECKPOINT 1 — one agent, three MCP tool servers on Cloud Run.

Prereq: the three tool servers deployed with `gcloud run deploy`, then `make check-mcp`
        (saves their URLs into .env).
Run:    adk web --port 8080 --allow_origins "*" checkpoints
        then Web Preview -> port 8080, pick m1_mcp_tools. --allow_origins is needed in
        Cloud Shell: Web Preview is a proxy, and adk web rejects other origins (403).
Ask:    "Where is my order ORD-1002 and is the oak chair in stock?"

This is the baseline the rest of the workshop improves on: one agent holding
every tool and making every decision.
"""

from google.adk.agents import LlmAgent

from shopdesk import config
from shopdesk.agents import gemini
from shopdesk.tools import mcp_toolset

root_agent = LlmAgent(
    name="support_agent",
    model=gemini(config.MODEL),
    description="Single agent with every tool — our baseline.",
    instruction=(
        "You are a ShopDesk support agent. Use the tools to answer questions about "
        "orders, stock and shipments. Never guess IDs, dates or prices."
    ),
    tools=[mcp_toolset("orders"), mcp_toolset("inventory"), mcp_toolset("shipping")],
)
