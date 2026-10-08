"""CHECKPOINT 1 — one agent, three MCP tool servers on Cloud Run.

Prereq: the three tool servers deployed with `gcloud run deploy`, then `make check-mcp`
        (saves their URLs into .env).
Run:    adk web --host 0.0.0.0 --port 8080 checkpoints   (then pick m1_mcp_tools)
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
