"""MODULE 6 — send the test scenarios to the deployed ShopDesk app.

    make bench          # every scenario once, against Agent Runtime (--runs 2 for more data)
    make report         # a few minutes later: numbers from Cloud Logging

Each turn is measured inside the app by MetricsPlugin (shopdesk/plugins/telemetry.py),
which writes one JSON record per turn to Cloud Logging. This script only sends
the messages and remembers which session was which scenario
(bench/runs.jsonl), so the report can score routing accuracy.

`--local` runs the same scenarios in Cloud Shell instead (no deploy needed),
writing the metrics straight to bench/metrics.jsonl.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.runtimes import find_app_runtime, stream_query  # noqa: E402

SCENARIOS = json.loads((ROOT / "bench" / "scenarios.json").read_text())


async def run_deployed(runs: int, out: Path):
    # Keep `client` referenced: when it's garbage-collected it closes the async session.
    client, app = find_app_runtime()
    with out.open("a", encoding="utf-8") as f:
        for r in range(runs):
            for sc in SCENARIOS:
                session = await app.async_create_session(user_id=sc["user"])
                t0 = time.perf_counter()
                authors = []
                try:
                    async for ev in stream_query(app, user_id=sc["user"], session_id=session["id"],
                                                 message=sc["message"]):
                        authors.append(ev.get("author"))
                except TimeoutError:
                    authors.append("TIMEOUT")  # the stream went quiet; move on to the next scenario
                ms = (time.perf_counter() - t0) * 1000
                f.write(json.dumps({"scenario": sc["id"], "run": r, "session_id": session["id"],
                                    "expect_route": sc["expect_route"], "client_ms": round(ms)}) + "\n")
                print(f"run {r} {sc['id']:<13} {ms:7.0f} ms  agents: {' > '.join(dict.fromkeys(a for a in authors if a))}")
    print("\nSent. Cloud Logging needs a minute or two; then: make report")


async def run_local(runs: int, out: Path):
    from google.adk.memory import InMemoryMemoryService
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from shopdesk.app import build_app
    from shopdesk.plugins.telemetry import MetricsPlugin

    app = build_app()
    metrics = next(p for p in app.plugins if isinstance(p, MetricsPlugin))
    metrics.metrics_file = ""
    runner = Runner(app=app, session_service=InMemorySessionService(), memory_service=InMemoryMemoryService())
    with out.open("a", encoding="utf-8") as f:
        for r in range(runs):
            for sc in SCENARIOS:
                s = await runner.session_service.create_session(app_name=app.name, user_id=sc["user"])
                async for _ in runner.run_async(user_id=sc["user"], session_id=s.id,
                        new_message=types.Content(role="user", parts=[types.Part(text=sc["message"])])):
                    pass
                rec = dict(metrics.finished[-1], scenario=sc["id"], run=r, expect_route=sc["expect_route"])
                f.write(json.dumps(rec) + "\n")
                print(f"run {r} {sc['id']:<13} {rec['duration_ms']:7.0f} ms")
    await runner.close()
    print(f"\nNow: python bench/report.py {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--local", action="store_true")
    a = ap.parse_args()
    if a.local:
        asyncio.run(run_local(a.runs, ROOT / "bench" / "metrics.jsonl"))
    else:
        asyncio.run(run_deployed(a.runs, ROOT / "bench" / "runs.jsonl"))
