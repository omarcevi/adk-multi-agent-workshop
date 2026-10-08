"""Module 4 — the production App: orchestrator + plugins + memory.

An `App` bundles the root agent with app-wide plugins. `adk web`, the Runner,
and Agent Runtime's AdkApp all accept it, so local and deployed behaviour match.
"""

from __future__ import annotations

from google.adk.apps import App

from shopdesk.agents.orchestrator import build_orchestrator
from shopdesk.plugins.guardrails import GuardrailPlugin
from shopdesk.plugins.memory import MemoryPlugin
from shopdesk.plugins.telemetry import MetricsPlugin


def build_app(*, name: str = "shopdesk", remote_agents=None) -> App:
    return App(
        name=name,
        root_agent=build_orchestrator(with_memory=True, remote_agents=remote_agents),
        plugins=[GuardrailPlugin(), MetricsPlugin(), MemoryPlugin()],
    )
