#!/usr/bin/env bash
# Start API + frontend together. Ctrl+C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Create it with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "Missing frontend/node_modules. Run: cd frontend && npm install"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

API_PID=""
FE_PID=""
CLEANING=0

cleanup() {
  # Prevent re-entry (kill used to signal the whole group and loop forever)
  if [[ "$CLEANING" -eq 1 ]]; then
    return
  fi
  CLEANING=1
  trap - EXIT INT TERM

  echo ""
  echo "Stopping Meeting Assist..."

  for pid in "$API_PID" "$FE_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      # Also stop any children (uvicorn reloader / vite)
      pkill -P "$pid" 2>/dev/null || true
    fi
  done

  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "API      → http://127.0.0.1:8000  (docs: /docs)"
echo "Frontend → http://127.0.0.1:5173"
echo ""

uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 &
API_PID=$!

(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173) &
FE_PID=$!

wait
