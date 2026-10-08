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
info() { printf '  \033[2m·\033[0m %s\n' "$*"; }
# run LOG LABEL CMD...: run a slow command with its output in .logs/LOG. While it
# runs, show LABEL, the seconds so far and the command's latest output line (on a
# terminal one line redrawn every second, otherwise a line every 15 s), so a long
# step visibly moves. On failure, print the end of the log and return its status.
run() {
  local log=".logs/$1" label="$2" start=$SECONDS rc=0 ticker; shift 2
  : > "$log"
  _ticker "$log" "$label" &
  ticker=$!
  # (Ctrl-C stops the foreground command; background jobs ignore it, so kill the ticker here.)
  trap 'kill "$ticker" 2>/dev/null || true' EXIT
  "$@" >> "$log" 2>&1 || rc=$?
  kill "$ticker" 2>/dev/null || true; wait "$ticker" 2>/dev/null || true
  trap - EXIT
  if [ -t 1 ]; then printf '\r\033[K'; fi
  if [ "$rc" = 0 ]; then
    ok "$label ($((SECONDS - start))s)"
  else
    bad "$label failed after $((SECONDS - start))s. End of $log:"
    tail -n 20 "$log" | sed 's/^/      /'
  fi
  return "$rc"
}
_ticker() {
  local log="$1" label="$2" start=$SECONDS i=0 last room
  local spin=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
  while :; do
    last=$(tail -n 1 "$log" 2>/dev/null | tr '\r' '\n' | tail -n 1 | sed 's/^ *//')
    if [ -t 1 ]; then
      # Stay on one line: a wrapped line can't be redrawn in place.
      room=$(( $(tput cols 2>/dev/null || echo 80) - ${#label} - 16 ))
      [ "$room" -gt 0 ] || room=0
      printf '\r\033[K  %s %s (%ss) \033[2m%s\033[0m' "${spin[i % 10]}" "$label" "$((SECONDS - start))" "${last:0:room}"
    elif [ "$i" -gt 0 ] && [ $((i % 15)) = 0 ]; then
      printf '  … %s, %ss so far: %s\n' "$label" "$((SECONDS - start))" "$last"
    fi
    i=$((i + 1))
    sleep 1
  done
}
need_project() {
  if [ -z "${GOOGLE_CLOUD_PROJECT:-}" ]; then
    echo "GOOGLE_CLOUD_PROJECT is not set. Run: make setup"; exit 1
  fi
}
runtime_sa() {
  local num; num=$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')
  echo "service-${num}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}
