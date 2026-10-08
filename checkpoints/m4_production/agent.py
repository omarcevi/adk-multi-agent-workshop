"""CHECKPOINT 4 — the full App: orchestrator + plugins + memory.
This is exactly what `make deploy-app` ships to Agent Runtime.

Run: `make web`, pick m4_production.
Try: the guardrail challenge (shopdesk/plugins/guardrails.py), a card number in
     your message, and "Please always contact me by SMS" then a new session.

`adk web` and Agent Runtime both pick up `app` before `root_agent`.
"""

from shopdesk.app import build_app

app = build_app(name="m4_production")  # app name must match the folder name
