#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "No .env found — copying .env.development"
    cp .env.development .env
fi

echo "Starting FastAPI backend..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
