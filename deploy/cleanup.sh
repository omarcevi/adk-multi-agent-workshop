#!/usr/bin/env bash
# make cleanup — delete everything the workshop deployed, so nothing keeps billing.
source "$(dirname "$0")/../scripts/common.sh"
need_project
echo "This deletes from $GOOGLE_CLOUD_PROJECT ($REGION):"
echo "  - Agent Runtime: every runtime named shopdesk-* (app and refunds specialist)"
echo "  - Cloud Run: shopdesk-{orders,inventory,shipping}-mcp (and the bonus policy server if present)"
echo "  - Artifact Registry repo 'shopdesk' and the staging bucket ${STAGING_BUCKET:-}"
echo "  - Bonus: the RAG Engine corpus 'shopdesk-policies' in ${RAG_REGION:-europe-west4} (billed while it exists)"
read -r -p "Continue? [y/N] " yn; [ "$yn" = "y" ] || exit 0
"$PY" - <<PYEOF
import agentplatform
c = agentplatform.Client(project="$GOOGLE_CLOUD_PROJECT", location="$REGION")
for r in list(c.runtimes.list()):
    if (r.api_resource.display_name or "").startswith("shopdesk"):
        try:
            c.runtimes.delete(name=r.api_resource.name, force=True)
            print("  deleted runtime", r.api_resource.display_name, r.api_resource.name.split("/")[-1])
        except Exception as e:
            print("  could not delete", r.api_resource.name, e)

# Bonus: the RAG corpus, found by name in case .env lost track of it. force=True also
# deletes its files (without it, a corpus that still has files can't be deleted).
from google.cloud import aiplatform_v1
region = "${RAG_REGION:-europe-west4}"
rag = aiplatform_v1.VertexRagDataServiceClient(client_options={
    "api_endpoint": f"{region}-aiplatform.googleapis.com", "quota_project_id": "$GOOGLE_CLOUD_PROJECT"})
try:
    for corpus in rag.list_rag_corpora(parent=f"projects/$GOOGLE_CLOUD_PROJECT/locations/{region}"):
        if corpus.display_name == "shopdesk-policies":
            rag.delete_rag_corpus(request={"name": corpus.name, "force": True}).result()
            print("  deleted RAG corpus", corpus.name.split("/")[-1], f"({region})")
except Exception as e:
    print("  could not check RAG corpora in", region, e)
PYEOF
for s in orders inventory shipping policy; do
  gcloud run services delete "shopdesk-$s-mcp" --region "$REGION" --quiet >/dev/null 2>&1 && ok "deleted shopdesk-$s-mcp" || true
done
gcloud artifacts repositories delete shopdesk --location "$REGION" --quiet >/dev/null 2>&1 && ok "deleted image repo" || true
[ -n "${STAGING_BUCKET:-}" ] && gcloud storage rm -r "$STAGING_BUCKET" --quiet >/dev/null 2>&1 && ok "deleted $STAGING_BUCKET" || true
for k in STAGING_BUCKET APP_RUNTIME_ID REFUNDS_RUNTIME_ID A2A_AGENT_CARDS ORDERS_MCP_URL INVENTORY_MCP_URL SHIPPING_MCP_URL POLICY_MCP_URL RAG_CORPUS; do envset "$k" ""; done
echo "Clean."
if gcloud artifacts repositories describe cloud-run-source-deploy --location "$REGION" >/dev/null 2>&1; then
  echo
  echo "Left alone: Artifact Registry repo 'cloud-run-source-deploy' in $REGION. The bonus's"
  echo "\`gcloud run deploy --source\` created it (if nothing else in this project did); it bills"
  echo "a little storage. Delete it if you don't use it:"
  echo "  gcloud artifacts repositories delete cloud-run-source-deploy --location $REGION"
fi
