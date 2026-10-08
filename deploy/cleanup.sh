#!/usr/bin/env bash
# make cleanup — delete everything the workshop deployed, so nothing keeps billing.
source "$(dirname "$0")/../scripts/common.sh"
need_project
echo "This deletes from $GOOGLE_CLOUD_PROJECT ($REGION):"
echo "  - Agent Runtime: every runtime named shopdesk-* (app and refunds specialist)"
echo "  - Cloud Run: shopdesk-{orders,inventory,shipping}-mcp (and the bonus policy server if present)"
echo "  - Artifact Registry repo 'shopdesk' and the staging bucket ${STAGING_BUCKET:-}"
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
PYEOF
for s in orders inventory shipping policy; do
  gcloud run services delete "shopdesk-$s-mcp" --region "$REGION" --quiet >/dev/null 2>&1 && ok "deleted shopdesk-$s-mcp" || true
done
gcloud artifacts repositories delete shopdesk --location "$REGION" --quiet >/dev/null 2>&1 && ok "deleted image repo" || true
[ -n "${STAGING_BUCKET:-}" ] && gcloud storage rm -r "$STAGING_BUCKET" --quiet >/dev/null 2>&1 && ok "deleted $STAGING_BUCKET" || true
for k in STAGING_BUCKET APP_RUNTIME_ID REFUNDS_RUNTIME_ID A2A_AGENT_CARDS ORDERS_MCP_URL INVENTORY_MCP_URL SHIPPING_MCP_URL POLICY_MCP_URL; do envset "$k" ""; done
echo "Clean."
