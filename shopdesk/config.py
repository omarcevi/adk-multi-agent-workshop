"""Central configuration, all from environment variables.

The same code runs in Cloud Shell (`adk web`) and on Agent Runtime. In Cloud
Shell the values come from `.env` (written by `make setup` and the deploy
targets); on Agent Runtime they are injected as the deployment's env vars.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # .env is optional; Agent Runtime injects env vars directly.
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # pragma: no cover
    pass

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
REGION = os.getenv("REGION", "us-central1")  # where Cloud Run + Agent Runtime deploy

# --- Models -----------------------------------------------------------------
# Gemini is called through the "global" endpoint, while Agent Runtime runs in
# REGION and sets GOOGLE_CLOUD_LOCATION to it. MODEL_LOCATION points model calls
# back at "global" without changing where the runtime itself lives.
if os.getenv("MODEL_LOCATION"):
    if os.getenv("GOOGLE_CLOUD_LOCATION"):
        os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION", os.environ["GOOGLE_CLOUD_LOCATION"])
    os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ["MODEL_LOCATION"]

MODEL = os.getenv("WORKSHOP_MODEL", "gemini-3.5-flash")
# The three parallel researchers use FAST_MODEL: the Module 6 lever for cost.
FAST_MODEL = os.getenv("WORKSHOP_FAST_MODEL", MODEL)

# --- MCP tool servers (Cloud Run URLs, saved to .env by `make check-mcp`) -----
MCP_URLS = {
    "orders": os.getenv("ORDERS_MCP_URL", ""),
    "inventory": os.getenv("INVENTORY_MCP_URL", ""),
    "shipping": os.getenv("SHIPPING_MCP_URL", ""),
    "policy": os.getenv("POLICY_MCP_URL", ""),  # bonus_rag/ only
}
# "google" = send a Google identity token (Cloud Run). "none" = plain HTTP (local tests).
MCP_AUTH = os.getenv("MCP_AUTH", "google")

# --- A2A ----------------------------------------------------------------------------
# Comma-separated agent-card URLs the orchestrator discovers at start-up
# (written to .env by `make card`).
A2A_AGENT_CARDS = [u.strip() for u in os.getenv("A2A_AGENT_CARDS", "").split(",") if u.strip()]
A2A_TIMEOUT_S = float(os.getenv("A2A_TIMEOUT_S", "120"))

# --- Guardrails (enforced by plugins, not prompts) ------------------------------
MAX_TOOL_CALLS_PER_TURN = int(os.getenv("MAX_TOOL_CALLS_PER_TURN", "12"))
MAX_LLM_CALLS_PER_TURN = int(os.getenv("MAX_LLM_CALLS_PER_TURN", "20"))
AUTO_REFUND_LIMIT = float(os.getenv("AUTO_REFUND_LIMIT", "150"))

# --- Telemetry --------------------------------------------------------------------
METRICS_FILE = os.getenv("METRICS_FILE", "")  # e.g. bench/metrics.jsonl
