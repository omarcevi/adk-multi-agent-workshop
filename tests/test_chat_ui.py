"""The chat + trace UI: stream format, event normalisation, agent tree."""

import asyncio
import json
import time

import httpx

from scripted_llm import call, script, text
from test_agents_offline import PIPELINE_PLANS
from ui.chat import LocalBackend, agent_tree, create_app, normalize


def test_normalize_accepts_snake_and_camel_case():
    t0 = time.time()
    snake = {"author": "intake", "timestamp": t0 + 1.5, "content": {"parts": [
        {"function_call": {"name": "get_order", "args": {"order_id": "ORD-1"}}}]},
        "usage_metadata": {"total_token_count": 42}, "actions": {"transfer_to_agent": "x"}}
    camel = {"author": "intake", "timestamp": t0 + 1.5, "content": {"parts": [
        {"functionCall": {"name": "get_order", "args": {"order_id": "ORD-1"}}}]},
        "usageMetadata": {"totalTokenCount": 42}, "actions": {"transferToAgent": "x"}}
    a, b = normalize(snake, t0), normalize(camel, t0)
    assert a == b and a["t"] == 1500 and a["tokens"] == 42 and a["transfer"] == "x"
    assert a["parts"][0] == {"kind": "call", "name": "get_order", "args": '{"order_id": "ORD-1"}'}
    assert normalize({"author": "x", "partial": True}, t0) is None


def test_agent_tree_marks_workflow_kinds():
    kinds = {r["name"]: r["kind"] for r in agent_tree()}
    assert kinds["shopdesk_orchestrator"] == "llm"
    assert kinds["support_pipeline"] == "sequential"
    assert kinds["research"] == "parallel"
    assert kinds["draft_review_loop"] == "loop"


def test_chat_stream_end_to_end_local_backend():
    from shopdesk.app import build_app

    app = build_app(name="ui_test", remote_agents=[])
    script(app.root_agent, {**PIPELINE_PLANS,
                            "shopdesk_orchestrator": [call("transfer_to_agent", agent_name="support_pipeline")]})
    backend = LocalBackend(app)

    async def go():
        transport = httpx.ASGITransport(app=create_app(backend))
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            info = (await c.get("/api/info")).json()
            page = await c.get("/")
            r = await c.post("/api/chat", json={"message": "My kettle lid from ORD-1001 is cracked", "user_id": "C-42"})
            return info, page, [json.loads(line) for line in r.text.splitlines() if line.strip()]

    info, page, msgs = asyncio.run(go())
    assert info["mode"] == "local" and any(n["kind"] == "parallel" for n in info["tree"])
    assert page.status_code == 200 and "chat + trace" in page.text
    assert msgs[0]["type"] == "session" and msgs[-1]["type"] == "done"
    events = [m for m in msgs if m["type"] == "event"]
    authors = {e["author"] for e in events}
    assert {"shopdesk_orchestrator", "intake", "order_researcher", "stock_researcher",
            "shipping_researcher", "drafter", "policy_reviewer"} <= authors
    assert any(e["transfer"] == "support_pipeline" for e in events)
    assert any(p["kind"] == "call" and p["name"] == "track_shipment" for e in events for p in e["parts"])
    assert sum(e["tokens"] for e in events) > 0
    assert all(e["t"] >= 0 for e in events)
    assert not [m for m in msgs if m["type"] == "error"]
