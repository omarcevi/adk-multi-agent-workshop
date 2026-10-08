# Shared shell helpers for the make targets. Sourced, not run.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
mkdir -p .logs
# Export everything in .env (KEY=VALUE lines) to this shell.
if [ -f .env ]; then set -a; . ./.env; set +a; fi
REGION="${REGION:-us-central1}"
envset() { "$PY" scripts/envfile.py set "$1" "$2"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
need_project() {
  if [ -z "${GOOGLE_CLOUD_PROJECT:-}" ]; then
    echo "GOOGLE_CLOUD_PROJECT is not set. Run: make setup"; exit 1
  fi
}
runtime_sa() {
  local num; num=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')
  echo "service-${num}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}
