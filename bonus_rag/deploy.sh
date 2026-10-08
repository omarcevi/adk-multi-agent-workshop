#!/usr/bin/env bash
# make bonus-rag — corpus + policy MCP server on Cloud Run + wire it into the reviewer.
source "$(dirname "$0")/../scripts/common.sh"
need_project
step "1/3 RAG Engine corpus from bonus_rag/policies/"
"$PY" bonus_rag/create_corpus.py
set -a; . ./.env; set +a

step "2/3 Policy MCP server -> Cloud Run"
NUM=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')
# The Cloud Run service runs as the default compute identity, which needs to query RAG Engine.
gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" --condition=None --quiet \
  --member="serviceAccount:${NUM}-compute@developer.gserviceaccount.com" --role=roles/aiplatform.user >/dev/null
gcloud run deploy shopdesk-policy-mcp --source bonus_rag --region "$REGION" --no-allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT,RAG_REGION=$RAG_REGION,RAG_CORPUS=$RAG_CORPUS" --quiet
URL=$(gcloud run services describe shopdesk-policy-mcp --region "$REGION" --format='value(status.url)')
envset POLICY_MCP_URL "$URL/mcp"
ok "policy server -> $URL/mcp"

step "3/3 Done"
echo "The policy reviewer now calls search_policy (shopdesk/agents/workflows.py, build_review_loop)."
echo "Try it: restart adk web -> m2_workflows. Ship it: run the Module 3 adk deploy command again with --agent_engine_id \$APP_RUNTIME_ID."
