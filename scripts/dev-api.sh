#!/bin/bash
# API (FastAPI/uvicorn) on http://127.0.0.1:8010 with auto-reload.
# Reads api/.env if present (see api/.env.example); defaults work locally.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/_common.sh"

PORT="${API_PORT:-$API_PORT_DEFAULT}"
ensure_root_env
ensure_venv "$ROOT/api" dev
if port_busy "$PORT"; then
  say "API: port $PORT artıq məşğuldur (API artıq işləyir?). Yenisi başladılmır."
  exit 0
fi
cd "$ROOT/api"
export PYTHONUNBUFFERED=1
say "API: http://127.0.0.1:$PORT"
exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port "$PORT"
