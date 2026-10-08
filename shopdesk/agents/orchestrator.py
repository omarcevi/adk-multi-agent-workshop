"""MODULE 3 — the orchestrator.

A coordinator LlmAgent that delegates (transfer) to:
* the local `support_pipeline` workflow (Sequential/Parallel/Loop), and
* every remote specialist discovered over A2A.

It never answers order questions itself; its whole job is routing, and it
routes on the *descriptions* of its sub-agents (for remote agents: their
agent cards). Better descriptions = better routing.

With `with_memory=True` it also recalls long-term memory before each turn
(Module 4); MemoryPlugin on the App saves each turn.

Look at:
  * INSTRUCTION          the routing rules
  * build_orchestrator() local workflow + discovered remote agents as sub-agents
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools import preload_memory

from shopdesk import config
from shopdesk.agents.discovery import discover_remote_agents
from shopdesk.agents.workflows import build_support_pipeline

INSTRUCTION = """\
You are the ShopDesk front desk. You never answer order questions yourself:
you pick the best specialist and transfer to it.

Routing rules:
- Order status, damaged items, exchanges, stock questions -> support_pipeline.
- Anything that needs money back -> the refunds specialist, if one is available.
  If no refunds specialist is available, say refunds are temporarily handled by email.
- Small talk or unclear requests -> answer briefly and ask one clarifying question.

If the customer tells you a lasting preference (language, contact channel, name),
acknowledge it; it will be remembered for next time.
"""


def build_orchestrator(*, with_memory: bool = False, remote_agents=None) -> LlmAgent:
    remotes = discover_remote_agents() if remote_agents is None else remote_agents
    return LlmAgent(
        name="shopdesk_orchestrator",
        model=config.MODEL,
        description="Front desk that routes customer requests to specialists.",
        instruction=INSTRUCTION,
        sub_agents=[build_support_pipeline(), *remotes],
        # Reads long-term memory into the prompt each turn. The write side is
        # shopdesk/plugins/memory.py (registered on the App).
        tools=[preload_memory] if with_memory else [],
    )
