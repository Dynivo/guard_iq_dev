#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "No .env found. Copy .env.example to .env and fill in the required values."
    exit 1
fi

echo "Starting FastAPI backend..."
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
