"""End-to-end wiring tests with a scripted model (no Gemini, no GCP needed).

They prove the architecture works: state flows Sequential -> Parallel -> Loop,
MCP tools really execute, the loop exits, the orchestrator delegates, plugins
enforce limits, telemetry records tokens per agent, and memory is written.
"""

import asyncio

from google.adk.apps import App
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from scripted_llm import call, script, text
from shopdesk.agents.orchestrator import build_orchestrator
from shopdesk.agents.refunds import build_refunds_agent
from shopdesk.agents.workflows import build_support_pipeline
from shopdesk.plugins.guardrails import GuardrailPlugin
from shopdesk.plugins.memory import MemoryPlugin
from shopdesk.plugins.telemetry import MetricsPlugin

CASE = '{"intent":"damaged_item","order_id":"ORD-1001","customer_id":"C-42","summary":"kettle lid cracked"}'

PIPELINE_PLANS = {
    "intake": [text(CASE)],
    "order_researcher": [call("get_order", order_id="ORD-1001"), text("- ORD-1001 delivered, kettle lid cracked")],
    "stock_researcher": [call("get_order", order_id="ORD-1001"), call("check_stock", sku="KTL-STEEL"),
                         text("- KTL-STEEL: 8 in stock")],
    "shipping_researcher": [call("get_order", order_id="ORD-1001"), call("track_shipment", tracking_id="TRK-7781"),
                            text("- delivered 2026-10-01")],
    "drafter": [text("Sorry Elif! We can send a replacement kettle (8 in stock).")],
    "policy_reviewer": [call("exit_loop"), text("APPROVED")],
}


async def _run(app: App, msg: str, memory=None):
    runner = Runner(app=app, session_service=InMemorySessionService(),
                    memory_service=memory or InMemoryMemoryService())
    session = await runner.session_service.create_session(app_name=app.name, user_id="u1")
    events = []
    async for ev in runner.run_async(user_id="u1", session_id=session.id,
                                     new_message=types.Content(role="user", parts=[types.Part(text=msg)])):
        events.append(ev)
    session = await runner.session_service.get_session(app_name=app.name, user_id="u1", session_id=session.id)
    await runner.close()
    return events, session


def test_pipeline_sequential_parallel_loop():
    pipeline = build_support_pipeline()
    script(pipeline, PIPELINE_PLANS)
    metrics = MetricsPlugin(metrics_file="")
    events, session = asyncio.run(_run(App(name="t", root_agent=pipeline, plugins=[metrics]),
                                       "My kettle lid from ORD-1001 is cracked"))
    st = session.state
    assert st["case"]["order_id"] == "ORD-1001"                 # structured output -> state
    assert {"order_facts", "stock_facts", "shipping_facts"} <= set(st)  # parallel fan-out
    assert "replacement" in st["draft"]
    authors = [e.author for e in events]
    assert authors.count("drafter") == 1                       # approved on round 1
    assert any(p.function_call and p.function_call.name == "exit_loop"
               for e in events for p in (e.content.parts if e.content else []))
    # MCP tool really ran: function response contains real data
    responses = [p.function_response.response for e in events for p in (e.content.parts if e.content else [])
                 if p.function_response]
    assert any("Kadikoy" in str(r) for r in responses)
    rec = metrics.finished[-1]
    assert rec["tokens"]["intake"]["total"] == 120
    assert rec["llm_calls"]["stock_researcher"] == 3


def test_refund_limit_plugin_blocks_tool():
    agent = build_refunds_agent()
    script(agent, {"refunds_specialist": [
        call("check_refund_eligibility", order_id="ORD-1004", reason="damaged"),
        call("issue_refund", order_id="ORD-1004", amount=420.0, reason="damaged"),
        text("Escalated to a human approver."),
    ]})
    guard = GuardrailPlugin(refund_limit=150)
    events, session = asyncio.run(_run(App(name="r", root_agent=agent, plugins=[guard]),
                                       "Refund ORD-1004 please, card 4111 1111 1111 1111"))
    assert guard.blocked and guard.blocked[0]["rule"] == "refund_limit"
    assert "last_refund_id" not in session.state            # tool never executed
    user_text = session.events[0].content.parts[0].text
    assert "4111" not in user_text and "[REDACTED CARD]" in user_text


def test_llm_budget_plugin_short_circuits():
    pipeline = build_support_pipeline()
    script(pipeline, PIPELINE_PLANS)
    guard = GuardrailPlugin(max_llm_calls=2)
    events, _ = asyncio.run(_run(App(name="b", root_agent=pipeline, plugins=[guard]), "where is ORD-1002"))
    assert any(b["rule"] == "llm_budget" for b in guard.blocked)


def test_orchestrator_delegates_and_remembers():
    orch = build_orchestrator(with_memory=True, remote_agents=[])
    script(orch, {**PIPELINE_PLANS,
                  "shopdesk_orchestrator": [call("transfer_to_agent", agent_name="support_pipeline")]})
    memory = InMemoryMemoryService()
    metrics = MetricsPlugin(metrics_file="")
    events, session = asyncio.run(_run(App(name="o", root_agent=orch, plugins=[metrics, MemoryPlugin()]),
                                       "My kettle lid from ORD-1001 is cracked", memory=memory))
    assert "draft" in session.state
    d = metrics.finished[-1]["delegations"]
    assert d and d[0]["to"] == "support_pipeline" and d[0]["outcome"] == "ok"
    found = asyncio.run(memory.search_memory(app_name="o", user_id="u1", query="kettle"))
    assert found.memories


def test_a2a_discovery_and_delegation():
    """Serve the refunds specialist over real A2A HTTP, discover it from its card,
    and let the orchestrator delegate to it."""
    import socket
    import threading
    import time

    import httpx
    import uvicorn
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    from shopdesk.agents.discovery import discover_remote_agents

    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    refunds = build_refunds_agent()
    script(refunds, {"refunds_specialist": [
        call("check_refund_eligibility", order_id="ORD-1001", reason="damaged"),
        call("issue_refund", order_id="ORD-1001", amount=20.0, reason="cracked lid"),
        text("Refunded 20 EUR for the cracked lid."),
    ]})
    guard = GuardrailPlugin()
    runner = Runner(app=App(name="refunds", root_agent=refunds, plugins=[guard]),
                    session_service=InMemorySessionService())
    server = uvicorn.Server(uvicorn.Config(to_a2a(refunds, host="127.0.0.1", port=port, runner=runner),
                                           host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=server.run, daemon=True); th.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(base, timeout=0.5); break
        except httpx.TransportError:
            time.sleep(0.1)
    try:
        card_url = f"{base}/.well-known/agent-card.json"
        remotes = discover_remote_agents([card_url, "http://127.0.0.1:1/nope.json"])  # 2nd is skipped
        assert [r.name for r in remotes] == ["refunds_specialist"]
        assert "refund" in remotes[0].description.lower()

        orch = build_orchestrator(with_memory=False, remote_agents=remotes)
        script(orch, {"shopdesk_orchestrator": [call("transfer_to_agent", agent_name="refunds_specialist")]})
        metrics = MetricsPlugin(metrics_file="")
        events, _ = asyncio.run(_run(App(name="o2", root_agent=orch, plugins=[metrics]),
                                     "Please refund the cracked lid on ORD-1001"))
        final = " ".join(p.text for e in events if e.content for p in e.content.parts if p.text)
        assert "Refunded 20 EUR" in final
        rec = metrics.finished[-1]
        assert rec["a2a_calls"][0]["agent"] == "refunds_specialist"
        assert rec["a2a_calls"][0]["outcome"] == "ok"
        assert rec["delegations"][0]["remote"] is True
    finally:
        server.should_exit = True; th.join(5)


def test_bench_report_runs(tmp_path, capsys):
    import sys as _sys
    _sys.path.insert(0, "bench")
    import report

    orch = build_orchestrator(with_memory=False, remote_agents=[])
    script(orch, {**PIPELINE_PLANS,
                  "shopdesk_orchestrator": [call("transfer_to_agent", agent_name="support_pipeline")]})
    metrics = MetricsPlugin(metrics_file=str(tmp_path / "m.jsonl"))
    asyncio.run(_run(App(name="o3", root_agent=orch, plugins=[metrics]), "kettle ORD-1001 cracked"))
    recs = report.load_file(tmp_path / "m.jsonl")
    recs[0].update(route_ok=True, scenario="damaged", routed_to="support_pipeline", expect_route="support_pipeline")
    report.report(recs)
    out = capsys.readouterr().out
    assert "support_pipeline" in out and "100%" in out and "Tokens per agent" in out
    print(out)
