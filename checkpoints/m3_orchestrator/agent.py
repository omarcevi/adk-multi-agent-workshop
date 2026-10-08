"""CHECKPOINT 3 — orchestrator delegating locally and over A2A
(code: shopdesk/agents/orchestrator.py, shopdesk/agents/discovery.py).

Prereq: `make status` shows the refunds specialist deployed, then `make card`.
Run:    `make web`, pick m3_orchestrator.
Ask:    "Where is ORD-1002?"  (-> support_pipeline, local)
        "Please refund 20 EUR for the cracked kettle lid on ORD-1001."  (-> A2A)
"""

from shopdesk.agents.orchestrator import build_orchestrator

root_agent = build_orchestrator(with_memory=False)
