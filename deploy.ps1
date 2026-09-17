# =============================================================================
# NIGCOMSAT PMS — Production Deployment Script for Windows Server
# =============================================================================
#
# USAGE:
#   .\deploy.ps1                          # Full interactive deployment
#   .\deploy.ps1 -SkipPrereqs              # Skip prerequisite installation
#   .\deploy.ps1 -SkipBuild               # Skip npm build (just configure & start)
#   .\deploy.ps1 -SkipMigrations           # Skip database migrations
#   .\deploy.ps1 -SkipPrereqs -SkipBuild   # Combine flags
#   .\deploy.ps1 -Configure               # Only configure .env files
#   .\deploy.ps1 -Start                    # Only start PM2 services
#   .\deploy.ps1 -Stop                     # Stop all PMS services
#   .\deploy.ps1 -Restart                  # Restart all PMS services
#   .\deploy.ps1 -Status                   # Show service status
#   .\deploy.ps1 -Logs                     # Tail live logs
#   .\deploy.ps1 -Uninstall                # Stop services & remove PM2 entries
#   .\deploy.ps1 -Firewall                 # Only configure Windows Firewall
#   .\deploy.ps1 -Check                    # Run prerequisite & config checks only
#
# REQUIREMENTS:
#   - Run as Administrator (for PostgreSQL, firewall, and service setup)
#   - Windows Server 2019+ or Windows 10/11 Pro
#   - Internet access for downloading packages (first run only)
#
# =============================================================================

param(
    [switch]$SkipPrereqs,
    [switch]$SkipBuild,
    [switch]$SkipMigrations,
    [switch]$Configure,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Status,
    [switch]$Logs,
    [switch]$Uninstall,
    [switch]$Firewall,
    [switch]$Check,
    [switch]$Force
)

$ErrorActionPreference = "Continue"

# =============================================================================
# CONFIGURATION — Edit these values before running
# =============================================================================

# Project paths — change if you deployed to a different location
$ScriptDir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPath    = Join-Path $ScriptDir "backend"
$FrontendPath   = Join-Path $ScriptDir "frontend"

# PostgreSQL — change these before running!
$PG_Host        = "localhost"
$PG_Port        = 5432
$PG_SuperUser   = "postgres"
$PG_AppUser     = "pms_user"
$PG_AppPassword = ""          # Leave blank — script will prompt you
$PG_AppDB       = "pms_db"

# Application defaults
$BackendPort    = 8000
$FrontendPort   = 3000
$ServerIP       = ""           # Leave blank — script will auto-detect

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-OK {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor Gray
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ServerIP {
    $ip = Get-NetIPAddress -AddressFamily IPv4 |
          Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.*" } |
          Select-Object -First 1 -ExpandProperty IPAddress
    if (-not $ip) {
        # Fallback
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" } | Select-Object -First 1).IPAddress
    }
    return $ip
}

function Confirm-Action {
    param(
        [string]$Prompt = "Continue?",
        [switch]$DefaultYes
    )
    if ($Force) { return $true }
    $choices = if ($DefaultYes) { "&Yes", "&No" } else { "&No", "&Yes" }
    $default = if ($DefaultYes) { 0 } else { 1 }
    $result = $Host.UI.PromptForChoice("", $Prompt, $choices, $default)
    return ($result -eq 0)
}

function Install-WingetPackage {
    param(
        [string]$Name,
        [string]$WingetId,
        [string]$DownloadUrl = "",
        [string]$VerifyCommand = ""
    )

    # Check if already installed
    if ($VerifyCommand) {
        $installed = Invoke-Expression $VerifyCommand 2>$null
        if ($LASTEXITCODE -eq 0 -and $installed) {
            Write-OK "$Name is already installed: $installed"
            return $true
        }
    }

    Write-Info "Installing $Name..."

    # Try winget first
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Info "Using winget to install $Name..."
        winget install --id $WingetId --accept-package-agreements --accept-source-agreements --silent 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-OK "$Name installed via winget"
            return $true
        }
    }

    # Fallback: provide download URL
    if ($DownloadUrl) {
        Write-Warn "winget not available or failed. Please install $Name manually:"
        Write-Host "  Download from: $DownloadUrl" -ForegroundColor Yellow
        if (Confirm-Action "Open download URL in browser?" -DefaultYes) {
            Start-Process $DownloadUrl
        }
        Write-Host ""
        Write-Host "Press Enter after installing $Name to continue..." -ForegroundColor Yellow
        Read-Host
        return $true
    }

    Write-Err "Could not install $Name automatically"
    return $false
}

# =============================================================================
# PREREQUISITE CHECKS & INSTALLATION
# =============================================================================

function Step-CheckPrerequisites {
    Write-Step "Step 1: Checking Prerequisites"

    $allGood = $true

    # --- Python ---
    Write-Host "Checking Python..." -ForegroundColor White
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        $pyVer = & python --version 2>&1
        Write-OK "Python found: $pyVer ($($py.Source))"
    } else {
        Write-Err "Python not found!"
        Write-Info "Install Python 3.11+ from https://www.python.org/downloads/"
        Write-Info "IMPORTANT: Check 'Add Python to PATH' during installation"
        $allGood = $false
    }

    # --- Node.js ---
    Write-Host "Checking Node.js..." -ForegroundColor White
    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        $nodeVer = & node --version 2>&1
        Write-OK "Node.js found: $nodeVer ($($node.Source))"
    } else {
        Write-Err "Node.js not found!"
        Write-Info "Install Node.js 20 LTS from https://nodejs.org/"
        $allGood = $false
    }

    # --- npm ---
    Write-Host "Checking npm..." -ForegroundColor White
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($npm) {
        $npmVer = & npm --version 2>&1
        Write-OK "npm found: $npmVer"
    } else {
        Write-Err "npm not found (comes with Node.js)"
        $allGood = $false
    }

    # --- PostgreSQL ---
    Write-Host "Checking PostgreSQL..." -ForegroundColor White
    $psql = Get-Command psql -ErrorAction SilentlyContinue
    if ($psql) {
        $pgVer = & psql --version 2>&1
        Write-OK "PostgreSQL found: $pgVer"
    } else {
        Write-Warn "PostgreSQL (psql) not found on PATH"
        Write-Info "If PostgreSQL is installed but not on PATH, the script can still proceed."
        Write-Info "Otherwise, install from https://www.postgresql.org/download/windows/"
        # Check if PG service exists even if psql isn't on PATH
        $pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
        if ($pgService) {
            Write-OK "PostgreSQL Windows service found: $($pgService.Name) ($($pgService.Status))"
        } else {
            Write-Err "No PostgreSQL service found either"
            $allGood = $false
        }
    }

    # --- PM2 ---
    Write-Host "Checking PM2..." -ForegroundColor White
    $pm2 = Get-Command pm2 -ErrorAction SilentlyContinue
    if ($pm2) {
        $pm2Ver = & pm2 --version 2>&1
        Write-OK "PM2 found: v$pm2Ver"
    } else {
        Write-Warn "PM2 not found. Will attempt to install..."
        npm install -g pm2 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-OK "PM2 installed successfully"
        } else {
            Write-Err "Failed to install PM2. Run: npm install -g pm2"
            $allGood = $false
        }
    }

    # --- Git (optional) ---
    Write-Host "Checking Git (optional)..." -ForegroundColor White
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        $gitVer = & git --version 2>&1
        Write-OK "Git found: $gitVer"
    } else {
        Write-Warn "Git not found (optional, needed only for git pull updates)"
    }

    Write-Host ""
    if ($allGood) {
        Write-OK "All prerequisites satisfied!"
    } else {
        Write-Err "Some prerequisites are missing. Please install them and re-run."
        if (-not (Confirm-Action "Continue anyway? (not recommended)" )) {
            exit 1
        }
    }
}

# =============================================================================
# CONFIGURE .ENV FILES
# =============================================================================

function Step-Configure {
    Write-Step "Step 2: Configuration"

    # --- Detect server IP ---
    if (-not $ServerIP) {
        $detectedIP = Get-ServerIP
        Write-Host "Detected server IP: $detectedIP" -ForegroundColor White
        $inputIP = Read-Host "Press Enter to accept, or type a different IP"
        if ($inputIP) {
            $Script:ServerIP = $inputIP
        } else {
            $Script:ServerIP = $detectedIP
        }
    }
    Write-OK "Using server IP: $ServerIP"

    # --- Configure backend .env ---
    Write-Host ""
    Write-Host "Configuring backend .env..." -ForegroundColor White

    $backendEnvPath = Join-Path $BackendPath ".env"

    if (Test-Path $backendEnvPath) {
        Write-Info "Found existing backend .env"
        $existingEnv = Get-Content $backendEnvPath -Raw
        Write-Info "Current contents:"
        Write-Host $existingEnv -ForegroundColor DarkGray
    } else {
        Write-Warn "No backend .env found — will create a new one"
    }

    # Prompt for database password
    if (-not $PG_AppPassword) {
        $PG_AppPassword = Read-Host "Enter password for PostgreSQL user '$PG_AppUser'" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($PG_AppPassword)
        $PG_AppPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    }

    # Prompt for secret key
    $generatedSecret = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 50 | ForEach-Object { [char]$_ })
    Write-Host ""
    Write-Host "Generated SECRET_KEY: $generatedSecret" -ForegroundColor DarkGray
    $secretInput = Read-Host "Press Enter to use this key, or paste your own"
    if (-not $secretInput) { $secretInput = $generatedSecret }

    $DATABASE_URL = "postgresql://${PG_AppUser}:${PG_AppPassword}@${PG_Host}:${PG_Port}/${PG_AppDB}"
    $CORS_ORIGINS = "http://${ServerIP}:${FrontendPort},http://localhost:${FrontendPort},http://${ServerIP}"

    $backendEnv = @"
DATABASE_URL=$DATABASE_URL
SECRET_KEY=$secretInput
CORS_ALLOWED_ORIGINS=$CORS_ORIGINS
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
"@

    Set-Content -Path $backendEnvPath -Value $backendEnv -Encoding UTF8
    Write-OK "Backend .env written to $backendEnvPath"

    # --- Configure frontend .env ---
    Write-Host ""
    Write-Host "Configuring frontend .env..." -ForegroundColor White

    $frontendEnvPath = Join-Path $FrontendPath ".env"

    # Ask whether using Nginx/IIS reverse proxy or direct ports
    Write-Host ""
    Write-Host "How will users access the app?" -ForegroundColor White
    Write-Host "  1) Direct: http://SERVER_IP:3000 (simpler, no extra setup)" -ForegroundColor Gray
    Write-Host "  2) Reverse proxy: http://SERVER_IP (port 80, needs IIS/Nginx)" -ForegroundColor Gray
    $proxyChoice = Read-Host "Enter 1 or 2 (default: 1)"
    if (-not $proxyChoice) { $proxyChoice = "1" }

    if ($proxyChoice -eq "2") {
        $API_URL = "http://${ServerIP}"
        $WS_URL = "ws://${ServerIP}"
    } else {
        $API_URL = "http://${ServerIP}:${BackendPort}"
        $WS_URL = "ws://${ServerIP}:${BackendPort}"
    }

    $frontendEnv = @"
# API Configuration
# Note: Do NOT include /api suffix - the frontend code adds it automatically
NEXT_PUBLIC_API_URL=$API_URL
NEXT_PUBLIC_WS_URL=$WS_URL
#
# Environment
NODE_ENV=production
"@

    Set-Content -Path $frontendEnvPath -Value $frontendEnv -Encoding UTF8
    Write-OK "Frontend .env written to $frontendEnvPath"
}

# =============================================================================
# POSTGRESQL SETUP
# =============================================================================

function Step-SetupDatabase {
    Write-Step "Step 3: PostgreSQL Database Setup"

    # Check if PostgreSQL is running
    $pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
    if (-not $pgService) {
        Write-Err "PostgreSQL service not found!"
        Write-Info "Install PostgreSQL first: https://www.postgresql.org/download/windows/"
        if (-not (Confirm-Action "Continue without database setup?")) { exit 1 }
        return
    }

    if ($pgService.Status -ne "Running") {
        Write-Warn "PostgreSQL service is not running. Starting it..."
        Start-Service $pgService.Name
        Start-Sleep -Seconds 3
    }
    Write-OK "PostgreSQL service is running"

    # Find psql path
    $psqlPath = Get-Command psql -ErrorAction SilentlyContinue
    if (-not $psqlPath) {
        # Try common PostgreSQL install paths
        $pgDirs = Get-ChildItem "C:\Program Files\PostgreSQL" -ErrorAction SilentlyContinue
        if ($pgDirs) {
            $latestPg = $pgDirs | Sort-Object Name -Descending | Select-Object -First 1
            $psqlExe = Join-Path $latestPg.FullName "bin\psql.exe"
            if (Test-Path $psqlExe) {
                $psqlPath = [System.Management.Automation.ApplicationInfo]::new($psqlExe)
                Write-Info "Found psql at: $psqlExe"
            }
        }
    }

    if (-not $psqlPath) {
        Write-Err "Cannot find psql. Is PostgreSQL installed?"
        Write-Info "Add PostgreSQL's bin folder to your PATH or install it."
        if (-not (Confirm-Action "Continue without database setup?")) { exit 1 }
        return
    }

    # Prompt for superuser password
    $pgSuperPassword = Read-Host "Enter PostgreSQL superuser (postgres) password" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pgSuperPassword)
    $pgSuperPasswordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

    # Set PGPASSWORD for non-interactive psql
    $env:PGPASSWORD = $pgSuperPasswordPlain

    # Check if database already exists
    $dbExists = & $psqlPath.Source -U $PG_SuperUser -h $PG_Host -p $PG_Port -t -c "SELECT 1 FROM pg_database WHERE datname='$PG_AppDB'" 2>$null

    if ($dbExists -match "1") {
        Write-OK "Database '$PG_AppDB' already exists"
    } else {
        Write-Host "Creating database and user..." -ForegroundColor Yellow
        & $psqlPath.Source -U $PG_SuperUser -h $PG_Host -p $PG_Port -c "CREATE USER $PG_AppUser WITH PASSWORD '$PG_AppPassword';" 2>$null
        & $psqlPath.Source -U $PG_SuperUser -h $PG_Host -p $PG_Port -c "CREATE DATABASE $PG_AppDB OWNER $PG_AppUser;" 2>$null
        & $psqlPath.Source -U $PG_SuperUser -h $PG_Host -p $PG_Port -c "GRANT ALL PRIVILEGES ON DATABASE $PG_AppDB TO $PG_AppUser;" 2>$null
        Write-OK "Database '$PG_AppDB' and user '$PG_AppUser' created"
    }

    # Verify connection
    $env:PGPASSWORD = $PG_AppPassword
    $testResult = & $psqlPath.Source -U $PG_AppUser -d $PG_AppDB -h $PG_Host -p $PG_Port -t -c "SELECT 1" 2>&1
    if ($testResult -match "1") {
        Write-OK "Database connection verified successfully"
    } else {
        Write-Err "Could not connect to database with app user!"
        Write-Host "Error: $testResult" -ForegroundColor Red
        if (-not (Confirm-Action "Continue anyway?")) { exit 1 }
    }

    Remove-Item Env:\PGPASSWORD
}

# =============================================================================
# PYTHON VENV & DEPENDENCIES
# =============================================================================

function Step-SetupBackend {
    Write-Step "Step 4: Backend Setup (Python)"

    Set-Location $BackendPath

    # --- Create venv ---
    $venvPath = Join-Path $BackendPath "venv"
    if (Test-Path $venvPath) {
        Write-OK "Virtual environment already exists at $venvPath"
    } else {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
        python -m venv venv
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to create virtual environment!"
            exit 1
        }
        Write-OK "Virtual environment created"
    }

    # --- Activate and install ---
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    & "$venvPath\Scripts\Activate.ps1"
    pip install -r requirements.txt --quiet 2>&1 | ForEach-Object {
        if ($_ -match "error|Error|ERROR|fail|Fail|FAIL") {
            Write-Err $_
        }
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Err "pip install failed! Check the errors above."
        deactivate
        exit 1
    }
    Write-OK "Python dependencies installed"

    # --- Run migrations ---
    if (-not $SkipMigrations) {
        Write-Host "Running database migrations..." -ForegroundColor Yellow
        alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Alembic migration failed!"
            deactivate
            exit 1
        }
        Write-OK "Database migrations applied"
    } else {
        Write-Warn "Skipping database migrations (-SkipMigrations flag)"
    }

    deactivate
}

# =============================================================================
# FRONTEND BUILD
# =============================================================================

function Step-SetupFrontend {
    Write-Step "Step 5: Frontend Setup (Next.js)"

    Set-Location $FrontendPath

    # --- npm install ---
    if (Test-Path "node_modules") {
        Write-OK "node_modules directory exists"
        Write-Host "Running npm install to check for updates..." -ForegroundColor Yellow
        npm install 2>&1 | Select-Object -Last 5
    } else {
        Write-Host "Installing npm dependencies (this may take a minute)..." -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Err "npm install failed!"
            exit 1
        }
    }
    Write-OK "npm dependencies ready"

    # --- Build ---
    if (-not $SkipBuild) {
        Write-Host "Building Next.js production bundle..." -ForegroundColor Yellow
        Write-Info "This takes 1-3 minutes..."

        npm run build 2>&1 | ForEach-Object {
            # Show progress lines
            if ($_ -match "Compiling|Creating|Generating|Route|error|Error|Failed") {
                Write-Host $_ -ForegroundColor Gray
            }
        }

        if ($LASTEXITCODE -ne 0) {
            Write-Err "Next.js build failed!"
            exit 1
        }
        Write-OK "Next.js production build complete"
    } else {
        Write-Warn "Skipping frontend build (-SkipBuild flag)"
    }
}

# =============================================================================
# PM2 SERVICE MANAGEMENT
# =============================================================================

function Step-UpdateEcosystemConfig {
    Write-Step "Step 6: PM2 Configuration"

    # --- Update backend ecosystem.config.js ---
    $backendEcosystemPath = Join-Path $BackendPath "ecosystem.config.js"
    $venvUvicornPath = (Join-Path $BackendPath "venv\Scripts\uvicorn.exe") -replace "\\", "\\\\"

    $backendEcosystem = @"
module.exports = {
  apps: [
    {
      name: "pms-backend",
      script: "$venvUvicornPath",
      args: "main:app --host 0.0.0.0 --port $BackendPort",
      cwd: "$($BackendPath -replace '\\','\\\\')",
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      env: {
        PYTHONUNBUFFERED: "1",
        PATH: "$venvPath\\Scripts;$($BackendPath -replace '\\','\\\\');%PATH%"
      },
      error_file: "./logs/backend-error.log",
      out_file: "./logs/backend-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z"
    }
  ]
};
"@

    Set-Content -Path $backendEcosystemPath -Value $backendEcosystem -Encoding UTF8
    Write-OK "Backend ecosystem.config.js updated"

    # --- Update frontend ecosystem.config.js ---
    $frontendEcosystemPath = Join-Path $FrontendPath "ecosystem.config.js"

    $frontendEcosystem = @"
module.exports = {
  apps: [{
    name: 'pms-frontend',
    script: 'node_modules/next/dist/bin/next',
    args: 'start -p $FrontendPort -H 0.0.0.0',
    interpreter: 'node',
    cwd: "$($FrontendPath -replace '\\','\\\\')",
    env: {
      NODE_ENV: 'production',
      NEXT_PUBLIC_API_URL: 'http://${ServerIP}:${BackendPort}',
      NEXT_PUBLIC_WS_URL: 'ws://${ServerIP}:${BackendPort}'
    },
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    error_file: "./logs/frontend-error.log",
    out_file: "./logs/frontend-out.log",
    log_date_format: "YYYY-MM-DD HH:mm:ss Z"
  }]
};
"@

    Set-Content -Path $frontendEcosystemPath -Value $frontendEcosystem -Encoding UTF8
    Write-OK "Frontend ecosystem.config.js updated"

    # --- Create log directories ---
    New-Item -ItemType Directory -Path (Join-Path $BackendPath "logs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $FrontendPath "logs") -Force | Out-Null
    Write-OK "Log directories created"
}

function Step-StartServices {
    Write-Step "Step 7: Starting Services"

    # Stop existing processes if any
    $existing = pm2 id pms-backend 2>$null
    if ($existing) {
        Write-Warn "PMS services already registered in PM2. Restarting..."
        pm2 restart pms-backend
        pm2 restart pms-frontend
        pm2 save
        pm2 list
        return
    }

    # Start backend
    Set-Location $BackendPath
    Write-Host "Starting backend..." -ForegroundColor Yellow
    pm2 start ecosystem.config.js
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to start backend!"
        pm2 logs pms-backend --lines 20 --nostream
        exit 1
    }

    # Start frontend
    Set-Location $FrontendPath
    Write-Host "Starting frontend..." -ForegroundColor Yellow
    pm2 start ecosystem.config.js
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to start frontend!"
        pm2 logs pms-frontend --lines 20 --nostream
        exit 1
    }

    # Wait a moment for processes to register
    Start-Sleep -Seconds 3

    # Verify
    pm2 list

    # Save
    pm2 save

    Write-OK "Services started!"
}

function Step-StopServices {
    Write-Step "Stopping PMS Services"
    pm2 stop pms-backend 2>$null
    pm2 stop pms-frontend 2>$null
    Write-OK "All PMS services stopped"
    pm2 list
}

function Step-Uninstall {
    Write-Step "Uninstalling PMS Services"
    pm2 delete pms-backend 2>$null
    pm2 delete pms-frontend 2>$null
    pm2 save
    Write-OK "All PMS processes removed from PM2"
    Write-Info "To fully remove PM2: npm uninstall -g pm2"
}

function Step-Status {
    Write-Step "PMS Service Status"
    pm2 list
    Write-Host ""
    Write-Host "Health check:" -ForegroundColor Cyan
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:$BackendPort/health" -TimeoutSec 5 -ErrorAction Stop
        Write-OK "Backend: $($health.status) - $($health.service)"
    } catch {
        Write-Err "Backend: Not responding on port $BackendPort"
    }
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$FrontendPort" -TimeoutSec 5 -ErrorAction Stop
        Write-OK "Frontend: HTTP $($response.StatusCode) on port $FrontendPort"
    } catch {
        Write-Err "Frontend: Not responding on port $FrontendPort"
    }
}

function Step-Logs {
    Write-Step "PMS Live Logs (Ctrl+C to stop)"
    pm2 logs pms-backend pms-frontend --lines 50
}

# =============================================================================
# WINDOWS FIREWALL
# =============================================================================

function Step-ConfigureFirewall {
    Write-Step "Step 8: Windows Firewall Configuration"

    # Check if running as admin
    if (-not (Test-Administrator)) {
        Write-Err "Firewall configuration requires Administrator privileges!"
        Write-Info "Re-run this script as Administrator: .\deploy.ps1 -Firewall"
        exit 1
    }

    # Remove existing rules if they exist (to update them)
    Remove-NetFirewallRule -DisplayName "PMS Frontend*" -ErrorAction SilentlyContinue
    Remove-NetFirewallRule -DisplayName "PMS Backend*" -ErrorAction SilentlyContinue

    # Add rules
    New-NetFirewallRule -DisplayName "PMS Frontend (TCP $FrontendPort)" `
        -Direction Inbound -LocalPort $FrontendPort -Protocol TCP -Action Allow `
        -Profile Domain,Private,Public | Out-Null
    Write-OK "Firewall rule: PMS Frontend (TCP $FrontendPort) — Allowed"

    New-NetFirewallRule -DisplayName "PMS Backend (TCP $BackendPort)" `
        -Direction Inbound -LocalPort $BackendPort -Protocol TCP -Action Allow `
        -Profile Domain,Private,Public | Out-Null
    Write-OK "Firewall rule: PMS Backend (TCP $BackendPort) — Allowed"

    Write-Host ""
    Write-OK "Firewall rules configured. The app is now accessible on the network."
}

# =============================================================================
# PM2 WINDOWS SERVICE (AUTO-START ON BOOT)
# =============================================================================

function Step-SetupAutoStart {
    Write-Step "Step 9: Auto-Start Configuration"

    # Check if pm2-windows-service is installed
    $pm2Service = Get-Service -Name "pm2" -ErrorAction SilentlyContinue
    if ($pm2Service) {
        Write-OK "PM2 Windows service already exists (Status: $($pm2Service.Status))"
        if ($pm2Service.Status -ne "Running") {
            Write-Host "Starting PM2 service..." -ForegroundColor Yellow
            Start-Service pm2
        }
        return
    }

    Write-Host "Setting up PM2 as a Windows service..." -ForegroundColor Yellow
    Write-Info "This ensures PMS starts automatically when the server boots."
    Write-Host ""

    if (-not (Test-Administrator)) {
        Write-Err "Auto-start setup requires Administrator privileges!"
        Write-Info "Re-run as Administrator: .\deploy.ps1 (the full deployment)"
        Write-Host ""
        Write-Host "Alternative: Use Windows Task Scheduler manually:" -ForegroundColor Yellow
        Write-Host '  1. Open Task Scheduler' -ForegroundColor Gray
        Write-Host '  2. Create Basic Task → Trigger: "At startup"' -ForegroundColor Gray
        Write-Host '  3. Action: "Start a program"' -ForegroundColor Gray
        Write-Host "  4. Program: pm2" -ForegroundColor Gray
        Write-Host "  5. Arguments: resurrect" -ForegroundColor Gray
        return
    }

    # Try to install pm2-windows-service
    $pm2ws = Get-Command pm2-service-install -ErrorAction SilentlyContinue
    if (-not $pm2ws) {
        Write-Host "Installing pm2-windows-service..." -ForegroundColor Yellow
        npm install -g pm2-windows-service 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Could not install pm2-windows-service automatically."
            Write-Info "You can set it up manually later with: npm install -g pm2-windows-service; pm2-service-install"
            return
        }
    }

    Write-Host ""
    Write-Host "Running pm2-service-install..." -ForegroundColor Yellow
    Write-Host "Accept the defaults when prompted." -ForegroundColor Gray
    pm2-service-install

    # Save current PM2 process list
    pm2 save

    Write-OK "PM2 auto-start configured"
}

# =============================================================================
# VERIFICATION
# =============================================================================

function Step-Verify {
    Write-Step "Step 10: Verification"

    $allGood = $true

    # --- Check PM2 processes ---
    Write-Host "Checking PM2 processes..." -ForegroundColor White
    pm2 list

    $backendOnline = pm2 id pms-backend 2>$null
    $frontendOnline = pm2 id pms-frontend 2>$null

    if ($backendOnline) {
        Write-OK "pms-backend is registered in PM2"
    } else {
        Write-Err "pms-backend is NOT running in PM2"
        $allGood = $false
    }

    if ($frontendOnline) {
        Write-OK "pms-frontend is registered in PM2"
    } else {
        Write-Err "pms-frontend is NOT running in PM2"
        $allGood = $false
    }

    # --- Health check ---
    Write-Host ""
    Write-Host "Checking backend health..." -ForegroundColor White
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:$BackendPort/health" -TimeoutSec 10 -ErrorAction Stop
        Write-OK "Backend health: $($health.status)"
    } catch {
        Write-Err "Backend is not responding on port $BackendPort"
        Write-Info "Check logs: pm2 logs pms-backend"
        $allGood = $false
    }

    Write-Host "Checking frontend..." -ForegroundColor White
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$FrontendPort" -TimeoutSec 10 -ErrorAction Stop
        Write-OK "Frontend responding (HTTP $($response.StatusCode))"
    } catch {
        Write-Err "Frontend is not responding on port $FrontendPort"
        Write-Info "Check logs: pm2 logs pms-frontend"
        $allGood = $false
    }

    # --- Summary ---
    Write-Host ""
    if ($allGood) {
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "  DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Backend:  http://localhost:$BackendPort" -ForegroundColor White
        Write-Host "  Frontend: http://localhost:$FrontendPort" -ForegroundColor White
        Write-Host "  API Docs: http://localhost:$BackendPort/docs" -ForegroundColor White
        Write-Host ""
        Write-Host "  From other computers on the network:" -ForegroundColor White
        Write-Host "  Frontend: http://${ServerIP}:$FrontendPort" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  Useful commands:" -ForegroundColor White
        Write-Host "    .\deploy.ps1 -Status    # Check service status" -ForegroundColor DarkGray
        Write-Host "    .\deploy.ps1 -Logs      # View live logs" -ForegroundColor DarkGray
        Write-Host "    .\deploy.ps1 -Restart  # Restart services" -ForegroundColor DarkGray
        Write-Host "    .\deploy.ps1 -Stop     # Stop services" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  To update the app:" -ForegroundColor White
        Write-Host "    1. Copy new files to the server (or git pull)" -ForegroundColor DarkGray
        Write-Host "    2. Run: .\deploy.ps1 -SkipPrereqs" -ForegroundColor DarkGray
        Write-Host "============================================================" -ForegroundColor Green
    } else {
        Write-Host "============================================================" -ForegroundColor Red
        Write-Host "  DEPLOYMENT INCOMPLETE — some checks failed" -ForegroundColor Red
        Write-Host "============================================================" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Troubleshooting:" -ForegroundColor Yellow
        Write-Host "    pm2 logs pms-backend    # View backend logs" -ForegroundColor Gray
        Write-Host "    pm2 logs pms-frontend   # View frontend logs" -ForegroundColor Gray
        Write-Host "    pm2 restart all         # Restart all services" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  Re-run deployment after fixing issues:" -ForegroundColor Yellow
        Write-Host "    .\deploy.ps1 -SkipPrereqs" -ForegroundColor Gray
        Write-Host "============================================================" -ForegroundColor Red
    }
}

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  NIGCOMSAT PMS — Production Deployment" -ForegroundColor Cyan
Write-Host "  Windows Server 2022" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Handle quick-action flags first
if ($Status) {
    Step-Status
    exit 0
}
if ($Logs) {
    Step-Logs
    exit 0
}
if ($Stop) {
    Step-StopServices
    exit 0
}
if ($Restart) {
    if (-not (Test-Administrator)) {
        Write-Warn "Some operations may require Administrator privileges."
    }
    pm2 restart pms-backend 2>$null
    pm2 restart pms-frontend 2>$null
    Start-Sleep -Seconds 2
    Step-Status
    exit 0
}
if ($Uninstall) {
    Step-Uninstall
    exit 0
}
if ($Firewall) {
    Step-ConfigureFirewall
    exit 0
}
if ($Check) {
    Step-CheckPrerequisites
    exit 0
}
if ($Configure) {
    Step-Configure
    exit 0
}
if ($Start) {
    Step-StartServices
    Step-Status
    exit 0
}

# --- Full deployment ---

# Admin check
if (-not (Test-Administrator)) {
    Write-Warn "Not running as Administrator. Some steps (firewall, auto-start) may fail."
    Write-Host "Re-run as Administrator for full deployment: " -ForegroundColor Yellow
    Write-Host "  Start-Process powershell -Verb RunAs -ArgumentList '-File `"$PSCommandPath`"' -NoNewWindow" -ForegroundColor Gray
    Write-Host ""
    if (-not (Confirm-Action "Continue without Administrator privileges?")) { exit 1 }
}

# Run all steps
if (-not $SkipPrereqs) { Step-CheckPrerequisites }
Step-Configure
Step-SetupDatabase
Step-SetupBackend
Step-SetupFrontend
Step-UpdateEcosystemConfig
Step-StartServices
Step-ConfigureFirewall
Step-SetupAutoStart
Step-Verify