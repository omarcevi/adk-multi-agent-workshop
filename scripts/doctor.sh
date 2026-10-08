#!/usr/bin/env bash
# make doctor — checks the usual setup problems and prints the fix for each.
source "$(dirname "$0")/common.sh"
fail=0
step "Environment"
[ -x .venv/bin/python ] && ok ".venv exists" || { bad ".venv missing -> make setup"; fail=1; }
[ -n "${GOOGLE_CLOUD_PROJECT:-}" ] && ok "project $GOOGLE_CLOUD_PROJECT, region $REGION" || { bad "no project in .env -> make setup"; exit 1; }
gcloud auth print-access-token >/dev/null 2>&1 && ok "gcloud signed in" || { bad "not signed in -> gcloud auth login"; fail=1; }

step "Billing and APIs"
BILLING=$(gcloud billing projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(billingEnabled)' 2>/dev/null || echo "")
[ "$BILLING" = "True" ] && ok "billing enabled" || { bad "billing not enabled (or not visible) -> link a billing account in the console"; fail=1; }
ENABLED=$(gcloud services list --enabled --format='value(config.name)' 2>/dev/null)
for api in aiplatform run cloudbuild artifactregistry cloudtrace logging; do
  echo "$ENABLED" | grep -q "^$api.googleapis.com$" && ok "$api API" || { bad "$api API off -> make setup"; fail=1; }
done

step "Deployments"
for v in ORDERS_MCP_URL INVENTORY_MCP_URL SHIPPING_MCP_URL; do
  [ -n "${!v:-}" ] && ok "$v set" || echo "  - $v not set yet (Module 1: gcloud run deploy, then make check-mcp)"
done
[ -n "${REFUNDS_RUNTIME_ID:-}" ] && ok "refunds specialist $REFUNDS_RUNTIME_ID" || echo "  - refunds specialist not deployed yet (Module 2: python deploy/refunds.py)"
[ -n "${APP_RUNTIME_ID:-}" ] && ok "app $APP_RUNTIME_ID" || echo "  - app not deployed yet, or not queried yet (Module 3: adk deploy agent_engine; make status)"
if [ -n "${REFUNDS_RUNTIME_ID:-}${APP_RUNTIME_ID:-}" ]; then
  SA=$(runtime_sa)
  ROLES=$(gcloud projects get-iam-policy "$GOOGLE_CLOUD_PROJECT" --flatten='bindings[].members' \
    --filter="bindings.members:serviceAccount:$SA" --format='value(bindings.role)' 2>/dev/null)
  echo "$ROLES" | grep -q "roles/run.invoker" && ok "Agent Runtime may call Cloud Run" || { bad "Agent Runtime can't call the tool servers -> bash scripts/grant_runtime_roles.sh"; fail=1; }
fi
echo; [ $fail = 0 ] && echo "All good." || echo "Fix the ✗ items above, then run make doctor again."
