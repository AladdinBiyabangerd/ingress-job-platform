#!/bin/bash
# Starts the API (8010), the site (3010) and the hourly collector together,
# with prefixed logs. Ctrl+C stops all of them.
#   ./scripts/dev.sh              all three
#   ./scripts/dev.sh api web      only the named parts (api, web, worker)
# First run also creates .env, the Python venvs and frontend/node_modules.
set -uo pipefail
. "$(cd "$(dirname "$0")" && pwd)/_common.sh"

parts=("$@")
[ ${#parts[@]} -gt 0 ] || parts=(api web worker)
for part in "${parts[@]}"; do
  case "$part" in
    api|web|worker) ;;
    *) die "naməlum hissə: $part (api, web, worker)" ;;
  esac
done

# Setup first, one after another, so the logs below stay readable.
ensure_root_env
for part in "${parts[@]}"; do
  case "$part" in
    api) ensure_venv "$ROOT/api" dev ;;
    web) ensure_node_modules ;;
    worker) ensure_venv "$ROOT/worker" ;;
  esac
done

set -m  # each part gets its own process group, so it can be stopped as a whole
pids=()

start() {
  local name="$1" color="$2" script="$3"
  local tag
  tag="$(printf '\033[%sm[%-6s]\033[0m ' "$color" "$name")"
  # A subshell, so $! is the leader of the process group holding the script,
  # its server and the log prefixer.
  ( "$ROOT/scripts/$script" 2>&1 | awk -v p="$tag" '{ print p $0; fflush() }' ) &
  pids+=("$!")
  disown "$!"  # no "Terminated" job notices on Ctrl+C
}

stop_all() {
  trap - INT TERM EXIT
  say ""
  say "dayandırılır..."
  local pid
  for pid in "${pids[@]:-}"; do
    [ -n "$pid" ] && kill -TERM -- "-$pid" 2>/dev/null
  done
  sleep 1
  for pid in "${pids[@]:-}"; do
    [ -n "$pid" ] && kill -KILL -- "-$pid" 2>/dev/null
  done
  exit 0
}
trap stop_all INT TERM EXIT

for part in "${parts[@]}"; do
  case "$part" in
    api) start api 36 dev-api.sh ;;
    web) start web 35 dev-web.sh ;;
    worker) start worker 33 dev-worker.sh ;;
  esac
done

say "İşləyir: ${parts[*]}. Sayt http://localhost:$WEB_PORT_DEFAULT, API http://127.0.0.1:$API_PORT_DEFAULT. Dayandırmaq: Ctrl+C"

# bash 3.2 has no "wait -n": poll until every part has exited.
while :; do
  alive=0
  for pid in "${pids[@]}"; do
    kill -0 "$pid" 2>/dev/null && alive=1
  done
  [ "$alive" -eq 1 ] || break
  sleep 1
done
trap - INT TERM EXIT
say "bütün hissələr dayandı"
