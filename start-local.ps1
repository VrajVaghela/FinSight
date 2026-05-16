<#
.SYNOPSIS
    FinSight AI - Local development startup script (no Docker for app services)
.DESCRIPTION
    Starts infrastructure (Postgres, Redis, Qdrant) via Docker, then launches
    all application services natively in separate PowerShell windows.
.USAGE
    .\start-local.ps1                 # Start everything
    .\start-local.ps1 -InfraOnly      # Start only infrastructure
    .\start-local.ps1 -SkipInfra      # Skip infrastructure, start only apps
    .\start-local.ps1 -StopAll        # Stop everything
#>
param(
    [switch]$InfraOnly,
    [switch]$SkipInfra,
    [switch]$StopAll
)

$ErrorActionPreference = "Continue"
$ROOT = $PSScriptRoot

# ──────────────────────────────────────────────
# Colors
# ──────────────────────────────────────────────
function Write-Step($msg) { Write-Host "`n[STEP] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [ERR] $msg" -ForegroundColor Red }

# ──────────────────────────────────────────────
# Helper: kill all FinSight-related processes
# ──────────────────────────────────────────────
function Stop-FinSightProcesses {
    # Kill by window title
    Get-Process | Where-Object { $_.MainWindowTitle -match "FinSight" } | Stop-Process -Force -ErrorAction SilentlyContinue
    # Kill any uvicorn/celery python processes on our ports
    $portPids = @()
    try {
        $portPids += (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
        $portPids += (Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue).OwningProcess
    } catch {}
    $portPids | Where-Object { $_ -and $_ -ne 0 } | Sort-Object -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
}

# ──────────────────────────────────────────────
# Stop everything
# ──────────────────────────────────────────────
if ($StopAll) {
    Write-Step "Stopping all services..."
    Stop-FinSightProcesses
    docker compose -f "$ROOT\docker-compose.infra.yml" down 2>$null
    Write-Ok "All services stopped."
    exit 0
}

# ──────────────────────────────────────────────
# Kill stale processes on our ports before starting
# ──────────────────────────────────────────────
Stop-FinSightProcesses

# ──────────────────────────────────────────────
# 1. Infrastructure (Docker - lightweight)
# ──────────────────────────────────────────────
if (-not $SkipInfra) {
    Write-Step "Starting infrastructure (Postgres, Redis, Qdrant) via Docker..."
    docker compose -f "$ROOT\docker-compose.infra.yml" up -d
    
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker infrastructure failed to start. Is Docker running?"
        exit 1
    }
    
    # Wait for Postgres to be ready
    Write-Host "  Waiting for Postgres..." -NoNewline
    $retries = 0
    do {
        Start-Sleep -Seconds 2
        $retries++
        Write-Host "." -NoNewline
        $ready = docker exec finsight-postgres pg_isready -U finsight 2>$null
    } while ($LASTEXITCODE -ne 0 -and $retries -lt 15)
    
    if ($retries -ge 15) {
        Write-Err "`nPostgres failed to become ready after 30s"
        exit 1
    }
    Write-Ok "Infrastructure is ready!"
}

if ($InfraOnly) {
    Write-Host "`n--- Infrastructure is running ---" -ForegroundColor Green
    Write-Host "  Postgres : localhost:5432"
    Write-Host "  Redis    : localhost:6379"
    Write-Host "  Qdrant   : localhost:6333"
    exit 0
}

# ──────────────────────────────────────────────
# 2. Clear Next.js cache (prevents stale proxy config)
# ──────────────────────────────────────────────
if (Test-Path "$ROOT\frontend\.next") {
    Remove-Item -Recurse -Force "$ROOT\frontend\.next" -ErrorAction SilentlyContinue
    Write-Ok "Cleared Next.js cache (.next)"
}

# ──────────────────────────────────────────────
# 3. Backend API (port 8000)
# ──────────────────────────────────────────────
Write-Step "Starting Backend API (port 8000)..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$ROOT\backend'; " +
    "`$env:PYTHONPATH='$ROOT\backend'; " +
    "`$Host.UI.RawUI.WindowTitle = 'FinSight: Backend API'; " +
    "Write-Host 'Starting Backend API on port 8000...' -ForegroundColor Cyan; " +
    "& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
)
Write-Ok "Backend API starting in new window"

# ──────────────────────────────────────────────
# 4. Celery Worker (backend)
# ──────────────────────────────────────────────
Write-Step "Starting Celery Worker..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$ROOT\backend'; " +
    "`$env:PYTHONPATH='$ROOT\backend'; " +
    "`$Host.UI.RawUI.WindowTitle = 'FinSight: Celery Worker'; " +
    "Write-Host 'Starting Celery Worker (solo pool for Windows)...' -ForegroundColor Cyan; " +
    "& .\.venv\Scripts\python.exe -m celery -A workers.celery_app worker --loglevel=info --pool=solo"
)
Write-Ok "Celery Worker starting in new window"

# ──────────────────────────────────────────────
# 5. Wait for Backend to be ready before starting Frontend
# ──────────────────────────────────────────────
Write-Host "`n  Waiting for Backend API..." -NoNewline
$retries = 0
$backendReady = $false
do {
    Start-Sleep -Seconds 1
    $retries++
    Write-Host "." -NoNewline
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $backendReady = $true }
    } catch {}
} while (-not $backendReady -and $retries -lt 30)

if ($backendReady) {
    Write-Ok "Backend API is ready!"
} else {
    Write-Warn "Backend may still be loading (check its terminal window)"
}

# ──────────────────────────────────────────────
# 6. Frontend (port 3000)
# ──────────────────────────────────────────────
Write-Step "Starting Frontend (port 3000)..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$ROOT\frontend'; " +
    "`$Host.UI.RawUI.WindowTitle = 'FinSight: Frontend'; " +
    "Write-Host 'Starting Next.js Frontend on port 3000...' -ForegroundColor Cyan; " +
    "npm run dev"
)
Write-Ok "Frontend starting in new window"

# ──────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────
Start-Sleep -Seconds 2
Write-Host "`n" -NoNewline
Write-Host "---------------------------------------------" -ForegroundColor Green
Write-Host ""
Write-Host "  Infrastructure (Docker):" -ForegroundColor White
Write-Host "    Postgres  -> localhost:5432" -ForegroundColor Gray
Write-Host "    Redis     -> localhost:6379" -ForegroundColor Gray
Write-Host "    Qdrant    -> localhost:6333" -ForegroundColor Gray
Write-Host ""
Write-Host "  Application (Native):" -ForegroundColor White
Write-Host "    Backend   -> http://localhost:8000      (API docs: /docs)" -ForegroundColor Gray
Write-Host "    Frontend  -> http://localhost:3000" -ForegroundColor Gray
Write-Host "    Celery    -> Background worker (solo pool)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Stop all:  .\start-local.ps1 -StopAll" -ForegroundColor Yellow
Write-Host "---------------------------------------------" -ForegroundColor Green
