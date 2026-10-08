#!/usr/bin/env bash
# make status — what's deployed, what's still building.
source "$(dirname "$0")/common.sh"
show() { # name label
  local log=".logs/$1.log" pid=".logs/$1.pid"
  if [ -f "$log" ] && grep -q '=== DONE ===' "$log"; then
    printf '  \033[32m✓\033[0m %-22s deployed\n' "$2"
  elif [ -f "$log" ] && grep -q '=== FAILED ===' "$log"; then
    printf '  \033[31m✗\033[0m %-22s failed -> see .logs/%s.log, then make doctor\n' "$2" "$1"
  elif [ -f "$pid" ] && kill -0 "$(cat "$pid")" 2>/dev/null; then
    printf '  \033[33m…\033[0m %-22s building  (%s)\n' "$2" "$(grep -v '^\s*$' "$log" | tail -1 | cut -c1-70)"
  else
    printf '  - %-22s not started\n' "$2"
  fi
}
step "ShopDesk on $GOOGLE_CLOUD_PROJECT ($REGION)"
[ -n "${ORDERS_MCP_URL:-}" ] && printf '  \033[32m✓\033[0m %-22s deployed\n' "MCP tool servers" || printf '  - %-22s not started\n' "MCP tool servers"
show refunds "refunds specialist"
show app "shopdesk app"
