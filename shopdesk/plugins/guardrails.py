"""MODULE 4 — programmatic constraints with an ADK plugin.

Prompts are suggestions; plugins are enforcement. A plugin is registered once on
the App/Runner and its callbacks run for *every* agent, model call and tool call
in that app, including sub-agents you did not write.

This plugin enforces three rules:
1. PII:     card-number-like strings are redacted before any model sees them.
2. Budget:  max LLM calls and max tool calls per user turn (stops runaway loops).
3. Money:   `issue_refund` above AUTO_REFUND_LIMIT is blocked and escalated.

Look at:
  * on_user_message_callback  redaction happens before ANY model sees the text
  * before_tool_callback      returning a dict skips the real tool entirely

CHALLENGE (Module 4): get the deployed refunds agent to refund the 420 EUR
desk on ORD-1004. Prompt tricks may convince the model; read the trace to see
where they stop.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Optional

from google.adk.models import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from shopdesk import config

log = logging.getLogger("shopdesk.guardrails")

CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")


class GuardrailPlugin(BasePlugin):
    def __init__(
        self,
        max_llm_calls: int = config.MAX_LLM_CALLS_PER_TURN,
        max_tool_calls: int = config.MAX_TOOL_CALLS_PER_TURN,
        refund_limit: float = config.AUTO_REFUND_LIMIT,
    ):
        super().__init__(name="guardrails")
        self.max_llm_calls = max_llm_calls
        self.max_tool_calls = max_tool_calls
        self.refund_limit = refund_limit
        self._llm_calls: dict[str, int] = defaultdict(int)
        self._tool_calls: dict[str, int] = defaultdict(int)
        self.blocked: list[dict[str, Any]] = []  # handy for tests and the demo

    # 1. PII redaction on the way in -------------------------------------------------
    async def on_user_message_callback(self, *, invocation_context, user_message):
        changed = False
        for part in user_message.parts or []:
            if part.text and CARD_RE.search(part.text):
                part.text = CARD_RE.sub("[REDACTED CARD]", part.text)
                changed = True
        return user_message if changed else None

    # 2a. LLM call budget -----------------------------------------------------------------
    async def before_model_callback(self, *, callback_context, llm_request) -> Optional[LlmResponse]:
        inv = callback_context.invocation_id
        self._llm_calls[inv] += 1
        if self._llm_calls[inv] > self.max_llm_calls:
            self._block("llm_budget", callback_context.agent_name, inv)
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="I've hit my processing limit for this request. "
                                           "A human agent will follow up.")],
                )
            )
        return None

    # 2b + 3. Tool budget and the refund limit ------------------------------------------
    async def before_tool_callback(self, *, tool, tool_args, tool_context) -> Optional[dict]:
        inv = tool_context.invocation_id
        self._tool_calls[inv] += 1
        if self._tool_calls[inv] > self.max_tool_calls:
            self._block("tool_budget", tool.name, inv)
            return {"error": "tool call budget exceeded for this request; stop calling tools"}

        if tool.name == "issue_refund":
            amount = float(tool_args.get("amount", 0) or 0)
            if amount > self.refund_limit:
                self._block("refund_limit", tool.name, inv, amount=amount)
                return {
                    "status": "needs_human_approval",
                    "message": f"Refunds above {self.refund_limit} require a human approver. "
                               "The request has been escalated; do not retry.",
                }
        return None

    async def after_run_callback(self, *, invocation_context) -> None:
        inv = invocation_context.invocation_id
        self._llm_calls.pop(inv, None)
        self._tool_calls.pop(inv, None)

    def _block(self, rule: str, target: str, inv: str, **extra) -> None:
        entry = {"rule": rule, "target": target, "invocation_id": inv, **extra}
        self.blocked.append(entry)
        log.warning("guardrail blocked: %s", entry)
