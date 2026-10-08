"""Exercise the exact A2A object we deploy to Agent Runtime, served locally.

shopdesk/a2a_service.py builds an `agentplatform` A2aAgent (HTTP+JSON,
card at /a2a/v1/card). Here we call its set_up(), mount its routes on a local
Starlette app, and let the orchestrator discover and delegate to it — the same
code path the deployed orchestrator uses, minus Google auth.
"""

import asyncio
import os
import socket
import sys
import threading
import time

import httpx
import uvicorn
from google.adk.apps import App
from starlette.applications import Starlette

from scripted_llm import call, script, text

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "demo-project")


def test_runtime_a2a_agent_round_trip(monkeypatch):
    import shopdesk.a2a_service as dep
    import shopdesk.agents.refunds as refunds_mod
    from test_agents_offline import _run

    from shopdesk.agents.discovery import discover_remote_agents
    from shopdesk.agents.orchestrator import build_orchestrator
    from shopdesk.plugins.telemetry import MetricsPlugin

    real_build = refunds_mod.build_refunds_agent

    def scripted_refunds():
        a = real_build()
        script(a, {"refunds_specialist": [
            call("check_refund_eligibility", order_id="ORD-1002", reason="late"),
            call("issue_refund", order_id="ORD-1002", amount=249.0, reason="late"),
            text("This refund needs a human approver; I've escalated it."),
        ]})
        return a

    monkeypatch.setattr(refunds_mod, "build_refunds_agent", scripted_refunds)
    monkeypatch.setenv("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION", "us-central1")

    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    a2a = dep.build_a2a_agent()
    a2a.set_up()
    a2a.agent_card.supported_interfaces[0].url = f"http://127.0.0.1:{port}/a2a"
    server = uvicorn.Server(uvicorn.Config(Starlette(routes=a2a.rest_routes),
                                           host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=server.run, daemon=True); th.start()
    card_url = f"http://127.0.0.1:{port}/a2a/v1/card"
    for _ in range(50):
        try:
            if httpx.get(card_url, timeout=0.5).status_code == 200:
                break
        except httpx.TransportError:
            time.sleep(0.1)
    try:
        remotes = discover_remote_agents([card_url])
        assert remotes and remotes[0].name == "refunds_specialist"
        orch = build_orchestrator(remote_agents=remotes)
        script(orch, {"shopdesk_orchestrator": [call("transfer_to_agent", agent_name="refunds_specialist")]})
        metrics = MetricsPlugin(metrics_file="")
        events, _ = asyncio.run(_run(App(name="rt", root_agent=orch, plugins=[metrics]),
                                     "My chair order ORD-1002 is late, refund it"))
        final = " ".join(p.text for e in events if e.content for p in e.content.parts if p.text)
        assert "human approver" in final
        assert metrics.finished[-1]["a2a_calls"][0]["outcome"] == "ok"
    finally:
        server.should_exit = True; th.join(5)
