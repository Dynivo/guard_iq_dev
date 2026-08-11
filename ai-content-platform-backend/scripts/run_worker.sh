#!/usr/bin/env bash
# Start Dramatiq workers for news ingest (requires Redis).
# Entrypoint: dramatiq app.workers  (NOT app.modules.jobs)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "No .env found — copying .env.development"
    cp .env.development .env
fi

# Workers only consume when the Redis broker is configured.
export JOB_BACKEND="${JOB_BACKEND:-dramatiq}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo "Starting Dramatiq workers (JOB_BACKEND=$JOB_BACKEND REDIS_URL=$REDIS_URL)..."
# Use 1 thread: each actor opens its own asyncio loop + NullPool engine.
# Extra threads are fine with worker_session, but 1 keeps ingest/scoring predictable.
dramatiq app.workers --processes 1 --threads 1
