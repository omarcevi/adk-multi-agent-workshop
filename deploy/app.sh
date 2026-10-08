#!/usr/bin/env bash
# make deploy-app — the full ShopDesk App (checkpoints/m4_production) -> Agent Runtime.
# Uses the standard `adk deploy agent_engine`: the App is built inside the cloud
# container from source, with managed sessions, Memory Bank and Cloud Trace.
source "$(dirname "$0")/../scripts/common.sh"
need_project
[ -n "${ORDERS_MCP_URL:-}" ] || { echo "Deploy the tool servers first: make deploy-mcp"; exit 1; }
[ -n "${A2A_AGENT_CARDS:-}" ] || echo "Note: no A2A_AGENT_CARDS yet; the app will deploy without the refunds specialist."

# adk deploy reads env vars for the deployment from the agent folder's .env.
# (GOOGLE_CLOUD_LOCATION is left out on purpose: it would change the region.)
# Agent Runtime rejects empty values, so unset optional ones (POLICY_MCP_URL,
# A2A_AGENT_CARDS) are dropped by the grep.
grep -v '=$' > checkpoints/m4_production/.env <<ENV
MODEL_LOCATION=global
WORKSHOP_MODEL=${WORKSHOP_MODEL:-gemini-3.5-flash}
WORKSHOP_FAST_MODEL=${WORKSHOP_FAST_MODEL:-${WORKSHOP_MODEL:-gemini-3.5-flash}}
ORDERS_MCP_URL=$ORDERS_MCP_URL
INVENTORY_MCP_URL=$INVENTORY_MCP_URL
SHIPPING_MCP_URL=$SHIPPING_MCP_URL
POLICY_MCP_URL=${POLICY_MCP_URL:-}
A2A_AGENT_CARDS=${A2A_AGENT_CARDS:-}
AUTO_REFUND_LIMIT=${AUTO_REFUND_LIMIT:-150}
MAX_TOOL_CALLS_PER_TURN=${MAX_TOOL_CALLS_PER_TURN:-25}
MAX_LLM_CALLS_PER_TURN=${MAX_LLM_CALLS_PER_TURN:-30}
ENV

# (plain string, not an array: macOS still ships bash 3.2)
UPDATE_FLAG=""
[ -n "${APP_RUNTIME_ID:-}" ] && UPDATE_FLAG="--agent_engine_id=$APP_RUNTIME_ID"
# --temp_folder: build outside checkpoints/, or a running `make web` lists the copy as an app.
.venv/bin/adk deploy agent_engine \
  --project "$GOOGLE_CLOUD_PROJECT" --region "$REGION" \
  --display_name shopdesk-app --otel_to_cloud \
  --extra_packages shopdesk $UPDATE_FLAG --temp_folder "$ROOT/.logs/app-build" \
  checkpoints/m4_production 2>&1 | tee .logs/app-deploy-raw.log

ID=$(grep -oE 'reasoningEngines/[0-9]+' .logs/app-deploy-raw.log | tail -1 | cut -d/ -f2)
[ -n "$ID" ] || { echo "Could not find the runtime ID in the deploy output"; exit 1; }
envset APP_RUNTIME_ID "$ID"
bash scripts/grant_runtime_roles.sh
echo "App deployed: reasoningEngines/$ID. Try: make query MSG=\"Where is ORD-1002?\""
