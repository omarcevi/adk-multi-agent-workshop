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
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/pip install -q -e .
ok "packages installed in .venv"

step "3/5 Google Cloud APIs (1-2 minutes)"
gcloud services enable aiplatform.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com cloudresourcemanager.googleapis.com iam.googleapis.com \
  cloudtrace.googleapis.com logging.googleapis.com monitoring.googleapis.com telemetry.googleapis.com \
  storage.googleapis.com --quiet
ok "APIs enabled"

step "4/5 Storage for builds"
gcloud artifacts repositories describe shopdesk --location="$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create shopdesk --repository-format=docker --location="$REGION" --quiet
ok "Artifact Registry repo 'shopdesk' in $REGION (tool-server image)"
BUCKET="gs://${PROJECT}-shopdesk-staging"
gcloud storage buckets describe "$BUCKET" >/dev/null 2>&1 || \
  gcloud storage buckets create "$BUCKET" --location="$REGION" --uniform-bucket-level-access --quiet
envset STAGING_BUCKET "$BUCKET"
ok "staging bucket $BUCKET (Agent Runtime uploads the refunds agent here)"

step "5/5 Permissions"
NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
# Cloud Build runs as the default compute service account in new projects.
for ROLE in roles/run.builder roles/artifactregistry.writer roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT" --condition=None --quiet \
    --member="serviceAccount:${NUM}-compute@developer.gserviceaccount.com" --role="$ROLE" >/dev/null 2>&1 || true
done
gcloud beta services identity create --service=aiplatform.googleapis.com --quiet >/dev/null 2>&1 || true
bash scripts/grant_runtime_roles.sh || echo "  (Agent Runtime identity not created yet; roles are granted again after the first deploy)"
ok "permissions set"

echo; echo "Setup done. Check anything odd with: make doctor"
