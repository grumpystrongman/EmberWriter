#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install -e "$BACKEND"

if [ ! -d "$FRONTEND/node_modules" ]; then
  (cd "$FRONTEND" && npm install)
fi

"$VENV/bin/python" -m uvicorn app.main:app --app-dir "$BACKEND" --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$FRONTEND"
npm run dev
