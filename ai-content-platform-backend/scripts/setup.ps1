# AI Content Platform — Setup Check (Windows)
Write-Host "=== AI Content Platform - Setup Check ===" -ForegroundColor Cyan
Write-Host ""

$missing = $false

function Check-Command($name) {
    if (Get-Command $name -ErrorAction SilentlyContinue) {
        Write-Host "  + $name found" -ForegroundColor Green
    } else {
        Write-Host "  x $name NOT FOUND" -ForegroundColor Red
        $script:missing = $true
    }
}

function Check-Port($name, $hostname, $port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect($hostname, $port)
        $tcp.Close()
        Write-Host "  + $name reachable on ${hostname}:${port}" -ForegroundColor Green
    } catch {
        Write-Host "  x $name NOT reachable on ${hostname}:${port}" -ForegroundColor Red
        $script:missing = $true
    }
}

Write-Host "-- Prerequisites --"
Check-Command "python"
Check-Command "pip"
Check-Command "psql"

Write-Host ""
Write-Host "-- Services --"
Check-Port "PostgreSQL" "localhost" 5432

Write-Host ""
if ($missing) {
    Write-Host "Some prerequisites are missing. Install them:" -ForegroundColor Yellow
    Write-Host "  - PostgreSQL: https://www.postgresql.org/download/windows/"
    Write-Host "  - Python 3.11+: https://www.python.org/downloads/"
    Write-Host ""
    Write-Host "  Then: createdb ai_content_platform"
    exit 1
}

Write-Host "All prerequisites found." -ForegroundColor Green
Write-Host ""
Write-Host "-- Quick start --"
Write-Host "  python -m venv .venv"
Write-Host "  .venv\Scripts\activate"
Write-Host "  pip install -r requirements.txt"
Write-Host "  copy .env.example .env"
Write-Host "  # Fill in secrets, including SEED_ADMIN_PASSWORD"
Write-Host "  createdb ai_content_platform"
Write-Host "  alembic upgrade head"
Write-Host "  python scripts\seed_database.py"
Write-Host "  uvicorn app.main:app --reload"
