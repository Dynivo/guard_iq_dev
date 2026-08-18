#!/usr/bin/env bash
set -euo pipefail

echo "=== AI Content Platform — Setup Check ==="
echo ""

MISSING=0

check_cmd() {
    if command -v "$1" &>/dev/null; then
        echo "  ✓ $1 found: $(command -v "$1")"
    else
        echo "  ✗ $1 NOT FOUND"
        MISSING=1
    fi
}

check_service() {
    local name="$1" host="$2" port="$3"
    if nc -z "$host" "$port" 2>/dev/null; then
        echo "  ✓ $name is reachable on $host:$port"
    else
        echo "  ✗ $name is NOT reachable on $host:$port"
        MISSING=1
    fi
}

echo "── Prerequisites ──"
check_cmd python3
check_cmd pip3
check_cmd psql

echo ""
echo "── Services ──"
check_service "PostgreSQL" "localhost" "5432"

echo ""
if [ "$MISSING" -ne 0 ]; then
    echo "Some prerequisites are missing. Install them before continuing:"
    echo ""
    echo "  macOS:"
    echo "    brew install postgresql@16 python@3.11"
    echo "    brew services start postgresql@16"
    echo ""
    echo "  Ubuntu/Debian:"
    echo "    sudo apt install postgresql python3 python3-pip python3-venv"
    echo "    sudo systemctl start postgresql"
    echo ""
    echo "  Then create the database:"
    echo "    createdb ai_content_platform"
    echo ""
    exit 1
fi

echo "All prerequisites found."
echo ""
echo "── Quick start ──"
echo "  python3 -m venv .venv"
echo "  source .venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  cp .env.example .env"
echo "  # Fill in secrets, including SEED_ADMIN_PASSWORD"
echo "  createdb ai_content_platform  # if not already created"
echo "  alembic upgrade head"
echo "  python scripts/seed_database.py"
echo "  uvicorn app.main:app --reload"
