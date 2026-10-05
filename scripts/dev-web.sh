#!/bin/bash
# Next.js site on http://localhost:3010 (npm run dev).
# Talks to the API on 127.0.0.1:8010 unless JOB_API_BASE_URL is set.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/_common.sh"

PORT="${WEB_PORT:-$WEB_PORT_DEFAULT}"
ensure_node_modules
if port_busy "$PORT"; then
  say "Sayt: port $PORT artıq məşğuldur (sayt artıq işləyir?). Yenisi başladılmır."
  exit 0
fi
cd "$ROOT/frontend"
say "Sayt: http://localhost:$PORT"
exec npx next dev --port "$PORT"
