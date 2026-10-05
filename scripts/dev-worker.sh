#!/bin/bash
# Collector: "python -m worker schedule" runs one pass now and then every hour.
# Reads the repo-root .env (API keys such as JOOBLE_API_KEY, REED_API_KEY).
# Only one scheduler runs at a time (file lock); a second start exits at once.
# One pass without the hourly loop: ./scripts/dev-worker.sh once
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/_common.sh"

ensure_root_env
ensure_venv "$ROOT/worker"
cd "$ROOT/worker"
export PYTHONUNBUFFERED=1
if [ "${1:-}" = "once" ]; then
  say "Toplayıcı: bir keçid"
  exec .venv/bin/python -m worker
fi
say "Toplayıcı: hər saat (ilk keçid indi)"
exec .venv/bin/python -m worker schedule
