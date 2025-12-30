#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$ROOT_DIR/venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Error: venv python not found at $VENV_PY"
  exit 1
fi

PORT="${PORT:-5001}"

"$VENV_PY" "$ROOT_DIR/app.py" &
APP_PID=$!

cleanup() {
  if kill -0 "$APP_PID" 2>/dev/null; then
    kill "$APP_PID"
  fi
}
trap cleanup EXIT

# Give the server a moment to start
sleep 1

URL="http://localhost:$PORT/"
if command -v open >/dev/null 2>&1; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"
else
  echo "Open this URL in your browser: $URL"
fi

wait "$APP_PID"
