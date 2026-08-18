#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/ai-content-platform-backend"
FRONTEND_DIR="$ROOT_DIR/ai-content-platform-frontend"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "Backend .env is missing. Complete INSTALLATION_GUIDE.md first."
  exit 1
fi
if [ ! -f "$FRONTEND_DIR/.env.local" ]; then
  echo "Frontend .env.local is missing. Complete INSTALLATION_GUIDE.md first."
  exit 1
fi
if [ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
  echo "Backend virtual environment is missing. Complete INSTALLATION_GUIDE.md first."
  exit 1
fi
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Frontend dependencies are missing. Complete INSTALLATION_GUIDE.md first."
  exit 1
fi

cleanup() {
  trap - EXIT INT TERM
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
  wait "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd "$BACKEND_DIR" && exec ./scripts/run_backend.sh) &
BACKEND_PID=$!
(cd "$FRONTEND_DIR" && exec ./scripts/run_frontend.sh) &
FRONTEND_PID=$!

echo "Starting Content Intelligence Platform..."
READY=0
for _ in $(seq 1 60); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "A service stopped during startup. Review the output above."
    exit 1
  fi
  if curl --silent --fail http://127.0.0.1:8000/api/v1/health >/dev/null; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "The backend did not become ready within 60 seconds."
  exit 1
fi

open http://127.0.0.1:3000
echo "The app is running at http://127.0.0.1:3000"
echo "Keep this Terminal window open. Press Control-C to stop the app."

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 2
done

echo "A service stopped unexpectedly. Review the output above."
exit 1
