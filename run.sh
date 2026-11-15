#!/usr/bin/env bash
set -euo pipefail

# Run from any directory; the Node launcher owns both development services.
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PORT="${PORT:-5173}"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required. Install Node.js, then run ./run.sh again." >&2
  exit 1
fi
if [[ ! -f frontend/node_modules/vite/bin/vite.js ]]; then
  echo "Frontend dependencies are missing. Run: cd frontend && npm install" >&2
  exit 1
fi

printf '\nStarting AskGaia frontend and backend…\n'
printf 'Open after Vite says ready: http://localhost:%s/\n' "$PORT"
printf 'Backend API: http://127.0.0.1:8001\n'
printf 'Keep this terminal open. Press Ctrl+C to stop services started here.\n'
printf 'If the frontend port is already occupied, stop the old server or use PORT=5174 ./run.sh\n\n'

exec node scripts/dev.mjs --host 127.0.0.1 --port "$PORT" --strictPort
