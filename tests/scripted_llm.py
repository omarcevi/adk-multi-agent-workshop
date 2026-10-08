"""A deterministic stand-in for Gemini so the wiring can be tested offline.

Each agent gets its own ScriptedLlm with a list of steps; every model call
returns the next step (a tool call or text) with fake token usage.
"""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types


def call(name: str, **args) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


def text(t: str) -> types.Part:
    return types.Part(text=t)


class ScriptedLlm(BaseLlm):
    model: str = "scripted"
    steps: list = []
    i: int = 0
    seen_requests: list = []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.seen_requests.append(llm_request)
        step = self.steps[min(self.i, len(self.steps) - 1)]
        self.i += 1
        parts = step if isinstance(step, list) else [step]
        yield LlmResponse(
            content=types.Content(role="model", parts=parts),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=100, candidates_token_count=20, total_token_count=120
            ),
        )


def script(agent, plans: dict[str, list]) -> None:
    """Replace the model of every agent in the tree that has a plan."""
    if agent.name in plans and hasattr(agent, "model"):
        agent.model = ScriptedLlm(steps=plans[agent.name])
    for sub in getattr(agent, "sub_agents", []) or []:
        script(sub, plans)
