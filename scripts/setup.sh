#!/usr/bin/env bash
# make setup — one time, in Cloud Shell. Safe to re-run.
source "$(dirname "$0")/common.sh"

step "1/5 Project"
PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
if [ -z "$PROJECT" ]; then
  echo "  No project selected. Run:  gcloud config set project <your-project-id>   then  make setup"; exit 1
fi
gcloud config set project "$PROJECT" --quiet >/dev/null
[ -f .env ] || cp .env.example .env
envset GOOGLE_CLOUD_PROJECT "$PROJECT"
envset REGION "$REGION"
ok "project $PROJECT, region $REGION (change REGION in .env before deploying, if you like)"

step "2/5 Python environment (about a minute)"
[ -d .venv ] || run venv.log "python3 -m venv .venv" python3 -m venv .venv
run pip-upgrade.log "pip install --upgrade pip" .venv/bin/pip install --upgrade pip
run pip-requirements.log "pip install -r requirements.txt" .venv/bin/pip install -r requirements.txt
run pip-shopdesk.log "pip install -e . (the shopdesk package)" .venv/bin/pip install -e .

step "3/5 Google Cloud APIs (1-2 minutes)"
APIS="aiplatform run cloudbuild artifactregistry cloudresourcemanager iam cloudtrace logging monitoring telemetry storage"
info "checking which APIs are already enabled"
ENABLED=" $(gcloud services list --enabled --format='value(config.name)' 2>/dev/null | tr '\n' ' ' || true) "
TODO=""
for API in $APIS; do
  case "$ENABLED" in *" $API.googleapis.com "*) ;; *) TODO="$TODO $API.googleapis.com" ;; esac
done
if [ -n "$TODO" ]; then
  info "enabling:$(echo "$TODO" | sed 's/\.googleapis\.com//g')"
  run apis.log "gcloud services enable ($(echo $TODO | wc -w | tr -d ' ') APIs)" gcloud services enable $TODO --quiet
else
  ok "all APIs already enabled"
fi

step "4/5 Storage for builds"
gcloud artifacts repositories describe shopdesk --location="$REGION" >/dev/null 2>&1 || \
  run artifact-repo.log "gcloud artifacts repositories create shopdesk" \
    gcloud artifacts repositories create shopdesk --repository-format=docker --location="$REGION" --quiet
ok "Artifact Registry repo 'shopdesk' in $REGION (tool-server image)"
BUCKET="gs://${PROJECT}-shopdesk-staging"
gcloud storage buckets describe "$BUCKET" >/dev/null 2>&1 || \
  run bucket.log "gcloud storage buckets create $BUCKET" \
    gcloud storage buckets create "$BUCKET" --location="$REGION" --uniform-bucket-level-access --quiet
envset STAGING_BUCKET "$BUCKET"
ok "staging bucket $BUCKET (Agent Runtime uploads the refunds agent here)"

step "5/5 Permissions"
NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
# Cloud Build runs as the default compute service account in new projects.
for ROLE in roles/run.builder roles/artifactregistry.writer roles/logging.logWriter; do
  info "$ROLE -> build service account (${NUM}-compute)"
  gcloud projects add-iam-policy-binding "$PROJECT" --condition=None --quiet \
    --member="serviceAccount:${NUM}-compute@developer.gserviceaccount.com" --role="$ROLE" >/dev/null 2>&1 || true
done
info "creating the Agent Runtime service identity"
gcloud beta services identity create --service=aiplatform.googleapis.com --quiet >/dev/null 2>&1 || true
bash scripts/grant_runtime_roles.sh || echo "  (Agent Runtime identity not created yet; roles are granted again after the first deploy)"
ok "permissions set"

"$PY" scripts/envfile.py sync
echo; echo "Setup done (full output of each step in .logs/). Next, in every Cloud Shell tab you use:  source env.sh"
echo "Check anything odd with: make doctor"
