"""MODULE 3 — dynamic A2A discovery.

The orchestrator is never told *who* the specialists are in code. It gets a
list of agent-card URLs (A2A_AGENT_CARDS), reads each card, and turns it into a
RemoteA2aAgent. The card's name, description and skills become the routing
information the orchestrator's model sees.

Adding a new specialist = deploy it, add its card URL. No code change here.

Look at:
  * discover_remote_agents()  card URL -> RemoteA2aAgent
  * _describe()               how a card's skills become routing text
"""

from __future__ import annotations

import logging
import re

import httpx
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

from shopdesk import config
from shopdesk.auth import GoogleAccessTokenAuth

log = logging.getLogger(__name__)


def _auth_for(url: str):
    # Agent Runtime only serves the card (and the agent) to authenticated callers.
    return GoogleAccessTokenAuth() if "googleapis.com" in url else None


def _safe_name(name: str) -> str:
    """Agent names must be valid identifiers."""
    s = re.sub(r"\W+", "_", name.strip().lower()).strip("_")
    return s if s and not s[0].isdigit() else f"agent_{s}"


def _describe(card: dict) -> str:
    desc = card.get("description", "")
    skills = card.get("skills") or []
    if skills:
        desc += " Skills: " + "; ".join(
            f"{s.get('name', s.get('id', ''))}: {s.get('description', '')}" for s in skills
        )
    return desc


def discover_remote_agents(card_urls: list[str] | None = None) -> list[RemoteA2aAgent]:
    """Fetch each card once at start-up and build RemoteA2aAgents.

    A card that can't be fetched is skipped with a warning, so one unhealthy
    specialist never takes the whole orchestrator down (Module 3's "pull the plug").
    """
    agents: list[RemoteA2aAgent] = []
    for url in card_urls if card_urls is not None else config.A2A_AGENT_CARDS:
        try:
            with httpx.Client(auth=_auth_for(url), timeout=15) as c:
                resp = c.get(url)
                resp.raise_for_status()
                card = resp.json()
        except Exception as e:  # noqa: BLE001
            log.warning("A2A discovery: skipping %s (%s)", url, e)
            continue
        agents.append(
            RemoteA2aAgent(
                name=_safe_name(card.get("name", "remote_agent")),
                description=_describe(card),
                agent_card=url,  # resolved again lazily, through the same authenticated client
                httpx_client=httpx.AsyncClient(auth=_auth_for(url), timeout=config.A2A_TIMEOUT_S),
                timeout=config.A2A_TIMEOUT_S,
            )
        )
        log.info("A2A discovery: registered %s from %s", agents[-1].name, url)
    return agents
