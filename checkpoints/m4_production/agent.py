"""CHECKPOINT 4 — the full App: orchestrator + plugins + memory.
This is exactly what `adk deploy agent_engine ... checkpoints/m4_production`
ships to Agent Runtime (its settings come from this folder's .env, which
scripts/envfile.py keeps in sync with the repo's .env).

Run: adk web ... checkpoints, pick m4_production.
Try: the guardrail challenge (shopdesk/plugins/guardrails.py), a card number in
     your message, and "Please always contact me by SMS" then a new session.

`adk web` and Agent Runtime both pick up `app` before `root_agent`.
"""

from shopdesk.app import build_app

app = build_app(name="m4_production")  # app name must match the folder name
