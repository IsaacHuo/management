#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"

cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/ before running smoke tests." >&2
  exit 1
fi

uv sync --frozen
uv run --no-sync python scripts/init_db.py --reset
uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >/tmp/library-management-smoke.log 2>&1 &
SERVER_PID="$!"
trap 'kill "$SERVER_PID" >/dev/null 2>&1 || true' EXIT

READY=0
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 0.3
done

if [[ "$READY" != "1" ]]; then
  echo "Server did not start in time. Last log lines:" >&2
  tail -40 /tmp/library-management-smoke.log >&2
  exit 1
fi

TOKEN="$(curl -fsS -X POST "http://127.0.0.1:${PORT}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"123456"}' \
  | uv run --no-sync python -c 'import json,sys; print(json.load(sys.stdin)["token"])')"

curl -fsS "http://127.0.0.1:${PORT}/api/dashboard/stats" \
  -H "Authorization: Bearer ${TOKEN}" >/dev/null

echo "Smoke test passed."
