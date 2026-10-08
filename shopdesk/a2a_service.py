"""MODULE 3 — the refunds specialist as an A2A service on Agent Runtime.

Two pieces:
  * the agent card: what other agents see when they discover this one
  * the executor: the ADK runner that answers A2A requests, with its plugins

These live inside the `shopdesk` package (not in the deploy script) because
Agent Runtime rebuilds them in the cloud container from this code.
"""

from __future__ import annotations


def build_executor():
    """Runs inside the Agent Runtime container: the ADK runner behind A2A."""
    from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
    from google.adk.apps import App
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from shopdesk.agents.refunds import build_refunds_agent
    from shopdesk.plugins.guardrails import GuardrailPlugin
    from shopdesk.plugins.telemetry import MetricsPlugin

    agent = build_refunds_agent()
    runner = Runner(
        app=App(
            name="refunds",
            root_agent=agent,
            # The guardrail travels with the agent that owns the money.
            plugins=[GuardrailPlugin(), MetricsPlugin(root_agent_name=agent.name)],
        ),
        session_service=InMemorySessionService(),
    )
    return A2aAgentExecutor(runner=runner)


def build_a2a_agent():
    """The deployable object: agent card + executor builder."""
    from a2a.types import AgentSkill
    from agentplatform.frameworks.a2a import A2aAgent, create_agent_card

    card = create_agent_card(
        agent_name="refunds_specialist",
        # TRY THIS (Module 3): the orchestrator routes on this text. Make it vague
        # ("helps customers"), redeploy (python deploy/refunds.py), restart adk web,
        # and watch routing get worse.
        description=(
            "Refunds specialist. Checks refund eligibility for an order and issues "
            "refunds (full or partial) for damaged, late or unwanted items."
        ),
        skills=[
            AgentSkill(
                id="refunds",
                name="Process refunds",
                description="Eligibility check plus full or partial refund for an order ID.",
                tags=["refund", "payments", "orders"],
                examples=["Refund the cracked kettle lid on ORD-1001"],
            )
        ],
        default_output_modes=["text/plain"],
    )
    return A2aAgent(agent_card=card, agent_executor_builder=build_executor)
