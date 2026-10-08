"""Tiny .env editor used by the helpers: `python scripts/envfile.py set KEY VALUE`.

Every write also refreshes checkpoints/m4_production/.env, which is where
`adk deploy agent_engine` reads the deployed app's environment from. That way
participants can run the raw `adk deploy` command without preparing anything.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
AGENT_ENV = ROOT / "checkpoints" / "m4_production" / ".env"

# What the deployed app needs. GOOGLE_CLOUD_LOCATION is deliberately absent: in an
# agent's .env, `adk deploy` would take it as the deploy region.
DEPLOY_KEYS = [
    "WORKSHOP_MODEL", "WORKSHOP_FAST_MODEL",
    "ORDERS_MCP_URL", "INVENTORY_MCP_URL", "SHIPPING_MCP_URL", "POLICY_MCP_URL",
    "A2A_AGENT_CARDS", "AUTO_REFUND_LIMIT", "MAX_TOOL_CALLS_PER_TURN", "MAX_LLM_CALLS_PER_TURN",
]


def _read(path: Path) -> list[str]:
    return path.read_text().splitlines() if path.exists() else []


def get_value(key: str, default: str = "") -> str:
    for line in _read(ENV):
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return default


def sync_agent_env() -> None:
    """Write the deploy subset of .env into the agent folder (empty values skipped:
    Agent Runtime rejects env vars without a value)."""
    lines = ["# Generated from ../../.env by scripts/envfile.py. Read by `adk deploy agent_engine`.",
             "MODEL_LOCATION=global"]
    for key in DEPLOY_KEYS:
        value = get_value(key)
        if value:
            lines.append(f"{key}={value}")
    AGENT_ENV.write_text("\n".join(lines) + "\n")


def set_value(key: str, value: str) -> None:
    out, done = [], False
    for line in _read(ENV):
        if line.split("=", 1)[0].strip() == key:
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    ENV.write_text("\n".join(out) + "\n")
    sync_agent_env()


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "set":
        set_value(args[0], args[1])
    elif cmd == "get":
        print(get_value(args[0], args[1] if len(args) > 1 else ""))
    elif cmd == "sync":
        sync_agent_env()
