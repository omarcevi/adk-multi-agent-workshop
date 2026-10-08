"""make card — show the refunds specialist's agent card, as the orchestrator sees it.

This is A2A discovery in one request: name, description and skills are what
the orchestrator's model routes on.
"""

import json

import httpx

from shopdesk import config
from shopdesk.auth import GoogleAccessTokenAuth

if not config.A2A_AGENT_CARDS:
    raise SystemExit("No card yet. Is the refunds specialist deployed? -> make status")
for url in config.A2A_AGENT_CARDS:
    card = httpx.get(url, auth=GoogleAccessTokenAuth(), timeout=30).raise_for_status().json()
    print(f"Card URL: {url}\n")
    print(json.dumps({k: card.get(k) for k in ("name", "description", "skills", "supportedInterfaces")}, indent=2))
print("\nThe URL is already in .env (A2A_AGENT_CARDS). Restart `make web` to pick it up.")
