# =============================================================================
# PM2 Startup Script for NIGCOMSAT PMS (Performance Management System)
# =============================================================================
# Starts both the backend (FastAPI/Uvicorn on port 8000) and frontend (Next.js
# on port 3000) using PM2 process manager.
#
# Usage:
#   .\pm2-startup.ps1                # Start both services (with migrations)
#   .\pm2-startup.ps1 -SkipMigrations # Start both services (skip DB migrations)
#   .\pm2-startup.ps1 -Dev           # Start in development mode (backend with --reload)
#   .\pm2-startup.ps1 -Stop          # Stop all PMS services
#   .\pm2-startup.ps1 -Restart       # Restart all PMS services
#   .\pm2-startup.ps1 -Status        # Show status of PMS services
#   .\pm2-startup.ps1 -Logs          # Tail logs for all PMS services
#   .\pm2-startup.ps1 -Clean         # Stop and delete all PMS PM2 processes
# =============================================================================

param(
    [switch]$SkipMigrations,
    [switch]$Dev,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Status,
    [switch]$Logs,
    [switch]$Clean
)

$ErrorActionPreference = "Continue"

# ---- Project paths ----
$ProjectRoot   = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPath   = Join-Path $ProjectRoot "backend"
$FrontendPath  = Join-Path $ProjectRoot "frontend"

# ---- PM2 process names (must match ecosystem.config.js) ----
$BackendProcessName  = "pms-backend"
$FrontendProcessName = "pms-frontend"

# ---- Helper functions ----

function Write-Banner {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  NIGCOMSAT Performance Management System - PM2 Manager" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Ensure-PM2 {
    $pm2Cmd = Get-Command pm2 -ErrorAction SilentlyContinue
    if (-not $pm2Cmd) {
        Write-Host "ERROR: PM2 is not installed or not on PATH." -ForegroundColor Red
        Write-Host "Install it with:  npm install -g pm2" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "[OK] PM2 found: $(pm2 --version)" -ForegroundColor Green
}

function Ensure-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Host "ERROR: .env file not found at $Path" -ForegroundColor Red
        Write-Host "Please create the .env file with DATABASE_URL and other secrets." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "[OK] .env file found at $Path" -ForegroundColor Green
}

function Ensure-LogsDir {
    param([string]$BasePath)
    $logsDir = Join-Path $BasePath "logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
        Write-Host "[OK] Created logs directory: $logsDir" -ForegroundColor Green
    }
}

function Run-Migrations {
    Write-Host ""
    Write-Host "--- Running Database Migrations ---" -ForegroundColor Yellow
    Push-Location $BackendPath
    try {
        $output = python -m alembic upgrade head 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Write-Host "[OK] Migrations applied successfully" -ForegroundColor Green
        } else {
            Write-Host "ERROR: Migration failed!" -ForegroundColor Red
            Write-Host $output -ForegroundColor Red
            Write-Host "Backend will not start. Fix migration errors and retry." -ForegroundColor Yellow
            exit 1
        }
    } finally {
        Pop-Location
    }
}

function Start-Backend {
    Write-Host ""
    Write-Host "--- Starting Backend (FastAPI on port 8000) ---" -ForegroundColor Yellow

    # Check if already registered in PM2
    $existing = pm2 id $BackendProcessName 2>$null | Select-String -Pattern "\d+" -SimpleMatch
    if ($existing) {
        Write-Host "[SKIP] Backend already registered in PM2 (use -Restart to restart)" -ForegroundColor DarkGray
        return
    }

    Push-Location $BackendPath
    try {
        if ($Dev) {
            # Development mode: use uvicorn directly with --reload
            pm2 start "main.py" `
                --name $BackendProcessName `
                --interpreter python `
                --env PYTHONUNBUFFERED=1 `
                --log "./logs/backend-out.log" `
                --error "./logs/backend-error.log" `
                --time
            Write-Host "[OK] Backend started in DEV mode (reload enabled)" -ForegroundColor Green
        } else {
            # Production mode: use uvicorn without reload via ecosystem config
            pm2 start ecosystem.config.js
            Write-Host "[OK] Backend started in PRODUCTION mode" -ForegroundColor Green
        }
    } finally {
        Pop-Location
    }
}

function Start-Frontend {
    Write-Host ""
    Write-Host "--- Starting Frontend (Next.js on port 3000) ---" -ForegroundColor Yellow

    # Check if already registered in PM2
    $existing = pm2 id $FrontendProcessName 2>$null | Select-String -Pattern "\d+" -SimpleMatch
    if ($existing) {
        Write-Host "[SKIP] Frontend already registered in PM2 (use -Restart to restart)" -ForegroundColor DarkGray
        return
    }

    Push-Location $FrontendPath
    try {
        if ($Dev) {
            # Development mode: use next dev
            pm2 start "node_modules/next/dist/bin/next" `
                --name $FrontendProcessName `
                --interpreter node `
                -- dev -p 3000 `
                --env NODE_ENV=development `
                --log "./logs/frontend-out.log" `
                --error "./logs/frontend-error.log" `
                --time
            Write-Host "[OK] Frontend started in DEV mode" -ForegroundColor Green
        } else {
            # Production mode: use ecosystem config (next start)
            pm2 start ecosystem.config.js
            Write-Host "[OK] Frontend started in PRODUCTION mode" -ForegroundColor Green
        }
    } finally {
        Pop-Location
    }
}

function Stop-Services {
    Write-Host ""
    Write-Host "--- Stopping PMS Services ---" -ForegroundColor Yellow
    pm2 stop $BackendProcessName  2>$null
    pm2 stop $FrontendProcessName 2>$null
    Write-Host "[OK] All PMS services stopped" -ForegroundColor Green
}

function Restart-Services {
    Write-Host ""
    Write-Host "--- Restarting PMS Services ---" -ForegroundColor Yellow
    pm2 restart $BackendProcessName  2>$null
    pm2 restart $FrontendProcessName 2>$null
    Write-Host "[OK] All PMS services restarted" -ForegroundColor Green
}

function Show-Status {
    Write-Host ""
    Write-Host "--- PMS Service Status ---" -ForegroundColor Cyan
    pm2 list | Select-String -Pattern $BackendProcessName, $FrontendProcessName, "Name" -SimpleMatch
    Write-Host ""
}

function Show-Logs {
    Write-Host ""
    Write-Host "--- Tailing PMS Logs (Ctrl+C to stop) ---" -ForegroundColor Cyan
    pm2 logs $BackendProcessName $FrontendProcessName --lines 50
}

function Clean-Services {
    Write-Host ""
    Write-Host "--- Removing PMS Processes from PM2 ---" -ForegroundColor Yellow
    pm2 delete $BackendProcessName  2>$null
    pm2 delete $FrontendProcessName 2>$null
    Write-Host "[OK] All PMS processes removed from PM2" -ForegroundColor Green
    Write-Host "Tip: Run this script without flags to start fresh." -ForegroundColor DarkGray
}

# ---- Main Logic ----

Write-Banner
Ensure-PM2

# Ensure log directories exist
Ensure-LogsDir $BackendPath
Ensure-LogsDir $FrontendPath

if ($Clean) {
    Clean-Services
    exit 0
}

if ($Stop) {
    Stop-Services
    exit 0
}

if ($Restart) {
    Ensure-EnvFile (Join-Path $BackendPath ".env")
    if (-not $SkipMigrations) { Run-Migrations }
    Restart-Services
    Show-Status
    exit 0
}

if ($Status) {
    Show-Status
    exit 0
}

if ($Logs) {
    Show-Logs
    exit 0
}

# ---- Default: Start both services ----

Ensure-EnvFile (Join-Path $BackendPath ".env")

if (-not $SkipMigrations) {
    Run-Migrations
} else {
    Write-Host "[SKIP] Migrations skipped (-SkipMigrations flag)" -ForegroundColor DarkGray
}

Start-Backend
Start-Frontend

# Give processes a moment to register
Start-Sleep -Seconds 2

Show-Status

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  PMS is running!" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "" -ForegroundColor White
Write-Host "  Useful commands:" -ForegroundColor White
Write-Host "    .\pm2-startup.ps1 -Status   # Check service status" -ForegroundColor DarkGray
Write-Host "    .\pm2-startup.ps1 -Logs     # View live logs" -ForegroundColor DarkGray
Write-Host "    .\pm2-startup.ps1 -Restart  # Restart services" -ForegroundColor DarkGray
Write-Host "    .\pm2-startup.ps1 -Stop     # Stop services" -ForegroundColor DarkGray
Write-Host "    .\pm2-startup.ps1 -Clean    # Remove from PM2" -ForegroundColor DarkGray
Write-Host "    pm2 save                    # Persist process list" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Green