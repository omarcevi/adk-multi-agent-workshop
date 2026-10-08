"""Module 6 — system telemetry as a plugin.

ADK already emits OpenTelemetry spans (invoke_agent, call_llm, execute_tool) and
gen_ai metrics. This plugin adds the *multi-agent* view on top:

* A2A routing latency   — wall time of each remote (A2A) agent call, plus time to first event
* Delegation success    — every hand-off from the orchestrator, with outcome ok / error / empty
* Tokens per agent      — prompt / output / total tokens, attributed to the agent that spent them

Each finished user turn produces one JSON record:
* printed to stdout as structured JSON  -> Cloud Logging on Agent Runtime
* appended to METRICS_FILE if set        -> bench/report.py locally
* recorded as OTel metrics               -> Cloud Monitoring when telemetry is enabled
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin
from opentelemetry import metrics

from shopdesk import config

_meter = metrics.get_meter("shopdesk")
_a2a_latency = _meter.create_histogram(
    "shopdesk.a2a.latency", unit="ms", description="Wall time of a remote A2A agent call"
)
_delegations = _meter.create_counter(
    "shopdesk.delegations", description="Hand-offs from the orchestrator, by target and outcome"
)
_tokens = _meter.create_counter("shopdesk.tokens", description="Tokens by agent and type")


@dataclass
class TurnRecord:
    invocation_id: str
    session_id: str
    started_at: float
    duration_ms: float = 0.0
    tokens: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    llm_calls: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tool_calls: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    delegations: list[dict[str, Any]] = field(default_factory=list)
    a2a_calls: list[dict[str, Any]] = field(default_factory=list)
    agent_ms: dict[str, float] = field(default_factory=dict)


def _is_remote(agent) -> bool:
    return type(agent).__name__ == "RemoteA2aAgent"


class MetricsPlugin(BasePlugin):
    def __init__(self, metrics_file: str | None = None, root_agent_name: str = "shopdesk_orchestrator"):
        super().__init__(name="multi_agent_metrics")
        self.metrics_file = metrics_file if metrics_file is not None else config.METRICS_FILE
        self.root = root_agent_name
        self.turns: dict[str, TurnRecord] = {}
        self.finished: list[dict[str, Any]] = []
        self._agent_start: dict[tuple[str, str], float] = {}
        # Per turn: timestamps of events, text events and errors. Workflow agents
        # never author events themselves (their children do), so outcomes are
        # judged by "what happened in the subtree since this agent started".
        self._event_ts: dict[str, list[float]] = defaultdict(list)
        self._text_ts: dict[str, float] = {}
        self._errors: dict[str, list[tuple[float, str]]] = defaultdict(list)

    # --- turn lifecycle ---------------------------------------------------------------------
    async def before_run_callback(self, *, invocation_context):
        inv = invocation_context.invocation_id
        self.turns[inv] = TurnRecord(inv, invocation_context.session.id, time.perf_counter())
        return None

    async def after_run_callback(self, *, invocation_context):
        inv = invocation_context.invocation_id
        for d in (self._event_ts, self._text_ts, self._errors):
            d.pop(inv, None)
        rec = self.turns.pop(inv, None)
        if not rec:
            return
        rec.duration_ms = round((time.perf_counter() - rec.started_at) * 1000, 1)
        out = {
            "kind": "shopdesk_turn_metrics",
            "invocation_id": rec.invocation_id,
            "session_id": rec.session_id,
            "duration_ms": rec.duration_ms,
            "tokens": {a: dict(t) for a, t in rec.tokens.items()},
            "llm_calls": dict(rec.llm_calls),
            "tool_calls": dict(rec.tool_calls),
            "delegations": rec.delegations,
            "a2a_calls": rec.a2a_calls,
            "agent_ms": rec.agent_ms,
        }
        self.finished.append(out)
        print(json.dumps(out), flush=True)  # structured log line
        if self.metrics_file:
            with open(self.metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(out) + "\n")

    # --- agents: latency + delegation outcome -------------------------------------------
    async def before_agent_callback(self, *, agent, callback_context):
        self._agent_start[(callback_context.invocation_id, agent.name)] = time.perf_counter()
        return None

    async def on_event_callback(self, *, invocation_context, event):
        inv = invocation_context.invocation_id
        now = time.perf_counter()
        self._event_ts[inv].append(now)
        if getattr(event, "error_code", None) or getattr(event, "error_message", None):
            self._errors[inv].append((now, str(event.error_message or event.error_code)))
        if event.content and any(p.text for p in (event.content.parts or [])):
            self._text_ts[inv] = now
        rec = self.turns.get(invocation_context.invocation_id)
        target = getattr(event.actions, "transfer_to_agent", None) if event.actions else None
        if rec is not None and target:
            rec.delegations.append({"from": event.author, "to": target, "outcome": "pending"})
        return None

    async def on_agent_error_callback(self, *, agent, callback_context, error):
        self._errors[callback_context.invocation_id].append((time.perf_counter(), repr(error)))

    async def after_agent_callback(self, *, agent, callback_context):
        inv = callback_context.invocation_id
        key = (inv, agent.name)
        start = self._agent_start.pop(key, None)
        rec = self.turns.get(inv)
        if start is None or rec is None:
            return None
        ms = round((time.perf_counter() - start) * 1000, 1)
        rec.agent_ms[agent.name] = ms
        errors = [msg for ts, msg in self._errors.get(inv, []) if ts >= start]
        error = errors[-1] if errors else None
        had_text = self._text_ts.get(inv, 0) >= start
        outcome = "error" if error else ("ok" if had_text else "empty")

        if _is_remote(agent):
            first = next((t for t in self._event_ts.get(inv, []) if t >= start), None)
            call = {
                "agent": agent.name,
                "latency_ms": ms,
                "time_to_first_event_ms": round((first - start) * 1000, 1) if first else None,
                "outcome": outcome,
                "error": error,
            }
            rec.a2a_calls.append(call)
            _a2a_latency.record(ms, {"agent": agent.name, "outcome": outcome})

        for d in rec.delegations:
            if d["to"] == agent.name and d["outcome"] == "pending":
                d.update(outcome=outcome, latency_ms=ms, remote=_is_remote(agent))
                _delegations.add(1, {"to": agent.name, "outcome": outcome})
                break
        return None

    # --- models + tools: tokens and call counts --------------------------------------
    async def after_model_callback(self, *, callback_context, llm_response):
        rec = self.turns.get(callback_context.invocation_id)
        if rec is None:
            return None
        name = callback_context.agent_name
        rec.llm_calls[name] += 1
        u = llm_response.usage_metadata
        if u:
            for kind, val in (
                ("prompt", u.prompt_token_count),
                ("output", u.candidates_token_count),
                ("thinking", getattr(u, "thoughts_token_count", None)),
                ("total", u.total_token_count),
            ):
                if val:
                    rec.tokens[name][kind] += val
                    _tokens.add(val, {"agent": name, "type": kind})
        return None

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        rec = self.turns.get(tool_context.invocation_id)
        if rec is not None:
            rec.tool_calls[f"{tool_context.agent_name}.{tool.name}"] += 1
        return None
