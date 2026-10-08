#!/usr/bin/env bash
# Run a slow deploy in the background: bg.sh <name> <command...>
# Output goes to .logs/<name>.log; `make status` reports progress.
source "$(dirname "$0")/common.sh"
name="$1"; shift
if [ -f ".logs/$name.pid" ] && kill -0 "$(cat ".logs/$name.pid")" 2>/dev/null; then
  echo "$name is already running (make status)"; exit 0
fi
nohup bash -c "$* && echo '=== DONE ===' || echo '=== FAILED ==='" > ".logs/$name.log" 2>&1 &
echo $! > ".logs/$name.pid"
echo "Started '$name' in the background (5-10 min). Carry on; check with: make status"
