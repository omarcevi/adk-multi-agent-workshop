"""ShopDesk chat + live trace (Modules 5 and 6).

    python ui/chat.py            # talk to your app deployed on Agent Runtime
    python ui/chat.py --local    # run the same App right here in Cloud Shell (no deploy needed)

Then Web Preview -> port 8080. Stop `adk web` first if it is using 8080 (or pass --port).

The page streams every event the agents produce and draws them as a timeline:
which agent ran when, which tools it called, where the A2A hop happened, and
how many tokens each agent spent.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402

KINDS = {"SequentialAgent": "sequential", "ParallelAgent": "parallel", "LoopAgent": "loop",
         "RemoteA2aAgent": "remote"}


# --- agent tree: lets the page draw parallel branches and loop rounds correctly -----
def agent_tree(root=None) -> list[dict]:
    if root is None:
        from shopdesk.agents.orchestrator import build_orchestrator

        root = build_orchestrator(remote_agents=[])  # remote agents appear when they speak
    rows: list[dict] = []

    def walk(agent, parent, depth):
        rows.append({"name": agent.name, "parent": parent, "depth": depth,
                     "kind": KINDS.get(type(agent).__name__, "llm")})
        for sub in getattr(agent, "sub_agents", []) or []:
            walk(sub, agent.name, depth + 1)

    walk(root, None, 0)
    return rows


# --- event normalisation: same output for local Event objects and Agent Runtime dicts --
def _get(d, *keys):
    if not isinstance(d, dict):
        return None
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def _short(value, limit=280) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


def normalize(ev: dict, t0: float) -> dict | None:
    if _get(ev, "partial"):
        return None  # streaming chunks; the final event carries the full content
    author = _get(ev, "author") or "?"
    ts = _get(ev, "timestamp")
    t_ms = round(((float(ts) if ts else time.time()) - t0) * 1000)
    parts = []
    for p in _get(_get(ev, "content") or {}, "parts") or []:
        if _get(p, "text") and not _get(p, "thought"):
            parts.append({"kind": "text", "text": p["text"]})
        fc = _get(p, "function_call", "functionCall")
        if fc:
            parts.append({"kind": "call", "name": _get(fc, "name"), "args": _short(_get(fc, "args") or {})})
        fr = _get(p, "function_response", "functionResponse")
        if fr:
            parts.append({"kind": "result", "name": _get(fr, "name"), "result": _short(_get(fr, "response") or {})})
    actions = _get(ev, "actions") or {}
    usage = _get(ev, "usage_metadata", "usageMetadata") or {}
    return {
        "author": author, "t": max(t_ms, 0), "parts": parts,
        "transfer": _get(actions, "transfer_to_agent", "transferToAgent"),
        "escalate": bool(_get(actions, "escalate")),
        "tokens": _get(usage, "total_token_count", "totalTokenCount") or 0,
        "error": _get(ev, "error_message", "errorMessage"),
    }


# --- backends -------------------------------------------------------------------------------
class LocalBackend:
    """The App from checkpoints/m4_production, running in this process."""

    mode = "local"

    def __init__(self, app=None):
        from google.adk.memory import InMemoryMemoryService
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        from shopdesk.app import build_app

        self.app = app or build_app(name="shopdesk")
        self.runner = Runner(app=self.app, session_service=InMemorySessionService(),
                             memory_service=InMemoryMemoryService())
        self.tree = agent_tree(self.app.root_agent)

    async def new_session(self, user_id: str) -> str:
        s = await self.runner.session_service.create_session(app_name=self.app.name, user_id=user_id)
        return s.id

    async def stream(self, user_id: str, session_id: str, message: str):
        from google.genai import types

        msg = types.Content(role="user", parts=[types.Part(text=message)])
        async for ev in self.runner.run_async(user_id=user_id, session_id=session_id, new_message=msg):
            yield ev.model_dump(mode="json", exclude_none=True)


class RuntimeBackend:
    """Your app on Agent Runtime, called with your own Google credentials."""

    mode = "deployed"

    def __init__(self):
        from scripts.runtimes import find_app_runtime

        self.client, self.runtime = find_app_runtime()  # keep client referenced (see scripts/runtimes.py)
        self.tree = agent_tree()

    async def new_session(self, user_id: str) -> str:
        return (await self.runtime.async_create_session(user_id=user_id))["id"]

    async def stream(self, user_id: str, session_id: str, message: str):
        async for ev in self.runtime.async_stream_query(user_id=user_id, session_id=session_id, message=message):
            yield ev


# --- web app ----------------------------------------------------------------------------------
def create_app(backend) -> Starlette:
    async def index(_):
        return FileResponse(Path(__file__).with_name("index.html"))

    async def info(_):
        from shopdesk import config

        return JSONResponse({"mode": backend.mode, "tree": backend.tree,
                             "project": config.PROJECT, "region": config.REGION})

    async def chat(request: Request):
        body = await request.json()
        user_id = body.get("user_id") or "C-42"
        message = (body.get("message") or "").strip()

        async def gen():
            t0 = time.time()
            try:
                session_id = body.get("session_id") or await backend.new_session(user_id)
                yield json.dumps({"type": "session", "session_id": session_id}) + "\n"
                async for raw in backend.stream(user_id, session_id, message):
                    item = normalize(raw, t0)
                    if item:
                        yield json.dumps({"type": "event", **item}, ensure_ascii=False) + "\n"
                yield json.dumps({"type": "done", "ms": round((time.time() - t0) * 1000)}) + "\n"
            except Exception as e:  # noqa: BLE001 - show it in the page, not just the terminal
                yield json.dumps({"type": "error", "message": f"{type(e).__name__}: {e}"}) + "\n"

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    return Starlette(routes=[Route("/", index), Route("/api/info", info),
                             Route("/api/chat", chat, methods=["POST"])])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", action="store_true", help="run the App here instead of calling Agent Runtime")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    import uvicorn

    backend = LocalBackend() if args.local else RuntimeBackend()
    where = "in this Cloud Shell" if args.local else "on Agent Runtime"
    print(f"ShopDesk chat ({where}) on port {args.port}: Web Preview -> Preview on port {args.port}")
    uvicorn.run(create_app(backend), host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
