"""CHECKPOINT 2 — Sequential + Parallel + Loop (code: shopdesk/agents/workflows.py).

Run: `make web`, pick m2_workflows.
Ask: "The kettle lid from ORD-1001 arrived cracked. Can I get a new one?"
Then open the Trace tab (the three researchers start together) and the State tab.
"""

from shopdesk.agents.workflows import build_support_pipeline

root_agent = build_support_pipeline()
