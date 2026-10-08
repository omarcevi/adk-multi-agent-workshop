#!/usr/bin/env bash
# Roles for Agent Runtime's identity: call the Cloud Run tool servers, call the
# other agent over A2A, use Gemini + Memory Bank, and write telemetry.
source "$(dirname "$0")/common.sh"
need_project
SA=$(runtime_sa)
for ROLE in roles/run.invoker roles/aiplatform.user roles/cloudtrace.agent roles/logging.logWriter roles/monitoring.metricWriter; do
  info "$ROLE -> Agent Runtime identity"
  gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" --condition=None --quiet \
    --member="serviceAccount:$SA" --role="$ROLE" >/dev/null
done
ok "Agent Runtime identity $SA can call Cloud Run, A2A and Gemini"
