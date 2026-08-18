#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm ci
fi

if [ ! -f "dist/index.html" ]; then
  echo "Building the frontend..."
  npm run build
fi

echo "Starting Content Intelligence frontend..."
echo "URL: http://localhost:3000"
exec npm run preview -- --host 127.0.0.1 --port 3000
