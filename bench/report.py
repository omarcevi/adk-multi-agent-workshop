"""Turn MetricsPlugin records into the numbers that matter for a multi-agent system.

    python bench/report.py --cloud-logging --hours 3   # deployed app (make report)
    python bench/report.py bench/metrics.jsonl          # local run (bench/run_bench.py --local)

Reports:
  1. End-to-end turn latency (p50/p95)
  2. A2A routing latency per remote agent (p50/p95, time to first event)
  3. Task delegation success rate (ok / empty / error) and routing accuracy
  4. Tokens per agent (avg per turn) and where the token budget goes
"""

import argparse
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))
    return xs[k]


def load_file(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_cloud_logging(hours: int, project: str | None):
    flt = 'jsonPayload.kind="shopdesk_turn_metrics" OR textPayload:"shopdesk_turn_metrics"'
    cmd = ["gcloud", "logging", "read", flt, f"--freshness={hours}h", "--format=json", "--limit=5000"]
    if project:
        cmd.append(f"--project={project}")
    rows = json.loads(subprocess.check_output(cmd))
    out = []
    for r in rows:
        if "jsonPayload" in r:
            out.append(r["jsonPayload"])
        else:
            try:
                out.append(json.loads(r.get("textPayload", "")))
            except json.JSONDecodeError:
                pass
    return out


def tag_routes(recs, runs_file):
    """Mark each turn with its scenario and whether the orchestrator routed it right."""
    try:
        runs = {r["session_id"]: r for r in load_file(runs_file)}
    except FileNotFoundError:
        return recs
    for rec in recs:
        run = runs.get(rec.get("session_id"))
        if run:
            routed = [d["to"] for d in rec.get("delegations", []) if d.get("from") == "shopdesk_orchestrator"]
            rec.update(scenario=run["scenario"], expect_route=run["expect_route"],
                       routed_to=routed[0] if routed else None,
                       route_ok=bool(routed) and routed[0] == run["expect_route"])
    return recs


def fmt(x, unit="ms"):
    return "-" if x is None else f"{x:,.0f} {unit}"


def report(recs):
    if not recs:
        print("No records yet. Cloud Logging can lag a minute or two; try again."); return
    # Turns handled by the orchestrator app. The refunds agent logs its own turns
    # too (it's a separate deployment); those count only towards tokens below.
    all_recs = recs
    recs = [r for r in recs if "shopdesk_orchestrator" in r.get("llm_calls", {})] or recs
    print(f"\n{len(recs)} customer turns ({len(all_recs) - len(recs)} more turns inside the refunds agent)\n")

    lat = [r["duration_ms"] for r in recs]
    print("1. End-to-end turn latency")
    print(f"   p50 {fmt(pct(lat, 50))}   p95 {fmt(pct(lat, 95))}   max {fmt(max(lat))}\n")

    a2a = defaultdict(list); ttfe = defaultdict(list)
    for r in recs:
        for c in r.get("a2a_calls", []):
            a2a[c["agent"]].append(c["latency_ms"])
            if c.get("time_to_first_event_ms") is not None:
                ttfe[c["agent"]].append(c["time_to_first_event_ms"])
    print("2. A2A routing latency (orchestrator -> remote agent -> answer)")
    if not a2a:
        print("   no A2A calls recorded")
    for agent, xs in a2a.items():
        print(f"   {agent:<22} n={len(xs):<3} p50 {fmt(pct(xs, 50))}  p95 {fmt(pct(xs, 95))}"
              f"  first event p50 {fmt(pct(ttfe[agent], 50))}")
    print()

    outcomes = defaultdict(Counter)
    for r in recs:
        for d in r.get("delegations", []):
            outcomes[d["to"]][d["outcome"]] += 1
    print("3. Task delegation success rate")
    for agent, c in outcomes.items():
        total = sum(c.values())
        print(f"   {agent:<22} {c['ok']}/{total} ok ({100*c['ok']/total:.0f}%)"
              f"  empty={c['empty']} error={c['error']}")
    routed = [r for r in recs if "route_ok" in r]
    if routed:
        ok = sum(r["route_ok"] for r in routed)
        print(f"   routing accuracy       {ok}/{len(routed)} ({100*ok/len(routed):.0f}%)")
        for r in routed:
            if not r["route_ok"]:
                print(f"     misroute: {r['scenario']} -> {r['routed_to']} (expected {r['expect_route']})")
    print()

    tok = defaultdict(list); calls = defaultdict(list)
    for r in all_recs:
        for agent, t in r.get("tokens", {}).items():
            tok[agent].append(t.get("total", 0))
        for agent, n in r.get("llm_calls", {}).items():
            calls[agent].append(n)
    grand = sum(sum(v) for v in tok.values()) or 1
    print("4. Tokens per agent (avg per turn where the agent ran)")
    print(f"   {'agent':<22} {'avg tokens':>10} {'avg LLM calls':>14} {'share':>7}")
    for agent, xs in sorted(tok.items(), key=lambda kv: -sum(kv[1])):
        print(f"   {agent:<22} {statistics.mean(xs):>10,.0f} {statistics.mean(calls[agent]):>14.1f}"
              f" {100*sum(xs)/grand:>6.0f}%")
    print(f"\n   avg tokens per turn (all agents): {grand/len(recs):,.0f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--cloud-logging", action="store_true")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--project")
    a = ap.parse_args()
    if a.cloud_logging:
        from pathlib import Path
        recs = load_cloud_logging(a.hours, a.project)
        report(tag_routes(recs, Path(__file__).resolve().parent / "runs.jsonl"))
    elif a.file:
        report(load_file(a.file))
    else:
        sys.exit("give a metrics file or --cloud-logging")
