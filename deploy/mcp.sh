#!/usr/bin/env bash
# make deploy-mcp — build ONE image, deploy it as THREE Cloud Run services.
# Unauthenticated access is off: only callers with roles/run.invoker get in.
source "$(dirname "$0")/../scripts/common.sh"
need_project
IMAGE="$REGION-docker.pkg.dev/$GOOGLE_CLOUD_PROJECT/shopdesk/mcp-servers:latest"

step "Building the tool-server image (about a minute)"
gcloud builds submit --tag "$IMAGE" --quiet . > .logs/mcp-build.log 2>&1 || { bad "build failed, see .logs/mcp-build.log"; exit 1; }
ok "$IMAGE"

step "Deploying orders, inventory, shipping in parallel"
for s in orders inventory shipping; do
  gcloud run deploy "shopdesk-$s-mcp" --image "$IMAGE" --region "$REGION" \
    --no-allow-unauthenticated --set-env-vars "MCP_SERVER=$s" \
    --cpu 1 --memory 512Mi --min-instances 0 --max-instances 3 --quiet \
    > ".logs/mcp-$s.log" 2>&1 &
done
wait
for s in orders inventory shipping; do
  url=$(gcloud run services describe "shopdesk-$s-mcp" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)
  [ -n "$url" ] || { bad "$s failed, see .logs/mcp-$s.log"; exit 1; }
  key="$(echo "$s" | tr a-z A-Z)_MCP_URL"
  envset "$key" "$url/mcp"
  ok "$s -> $url/mcp"
done
echo; echo "URLs saved to .env. Next: make check-mcp"
