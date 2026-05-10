#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/ before deployment." >&2
  exit 1
fi

uv sync --frozen --no-dev
uv run --no-sync python scripts/init_db.py

echo "Library Management System is starting at http://${HOST}:${PORT}"
echo "Default admin: admin / 123456"
echo "Please change the default password after first deployment."

exec uv run --no-sync uvicorn app.main:app --host "$HOST" --port "$PORT"
