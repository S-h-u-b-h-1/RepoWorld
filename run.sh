#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi
PORT="${PORT:-8004}"
export APP_BASE_URL="${APP_BASE_URL:-http://127.0.0.1:$PORT}"
export APP_ENV="${APP_ENV:-development}"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
