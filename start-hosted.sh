#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: ./start-hosted.sh <firebase-project-id>" >&2
  exit 1
fi

FIREBASE_PROJECT_ID="$1"
if [[ ! "$FIREBASE_PROJECT_ID" =~ ^[a-z0-9-]+$ ]]; then
  echo "Firebase project ID must contain only lowercase letters, digits, and hyphens." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
VENV="$BACKEND/.venv"
HOSTED_URL="https://$FIREBASE_PROJECT_ID.web.app"
export EMBER_DATA_DIR="${EMBER_DATA_DIR:-$ROOT/data}"

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install -e "$BACKEND"
export EMBER_CORS_ORIGINS="https://$FIREBASE_PROJECT_ID.web.app,https://$FIREBASE_PROJECT_ID.firebaseapp.com"

echo "EmberWriter hosted UI: $HOSTED_URL"
echo "EmberWriter local API: http://127.0.0.1:8000"
echo "Project data: $EMBER_DATA_DIR"
echo "Keep this terminal open while using the hosted UI. Press Ctrl+C to stop the API."

cd "$ROOT"
"$VENV/bin/python" -m uvicorn app.main:app --app-dir "$BACKEND" --host 127.0.0.1 --port 8000
