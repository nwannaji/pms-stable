# 🚀 PMS Deployment Guide: Windows Server 2022 → pms.nigcomsat.gov.ng

## Architecture Overview

```
Internet (HTTPS)
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  IIS Reverse Proxy (port 80/443)                     │
│  pms.nigcomsat.gov.ng                                 │
│                                                       │
│  /api/*            ──► http://160.226.0.67:8000 (FastAPI) │
│  /api/notifications/ws ► ws://160.226.0.67:8000 (WebSocket) │
│  /*                 ──► http://localhost:3000 (Next.js)    │
└──────────────────────────────────────────────────────┘
```

---

## STEP 1: DNS Configuration (Do this FIRST)

Before anything else, point your domain to the server:

1. Log into your DNS provider (likely your internal DNS or NIGCOMSAT's domain registrar)
2. Create an **A Record**:
   - **Name**: `pms`
   - **Domain**: `nigcomsat.gov.ng`
   - **Value**: `<your-server-public-IP>`
   - **TTL**: 3600 (or lower for faster propagation)

3. Verify DNS propagation (from any machine):
   ```powershell
   nslookup pms.nigcomsat.gov.ng
   # Should resolve to your server's public IP
   ```

---

## STEP 2: Install Prerequisites on the Server

Open **PowerShell as Administrator** on the remote server (via RDP):

### 2a. Install Python 3.11+

```powershell
winget install Python.Python.3.11
```

After install, **close and reopen PowerShell**, then verify:
```powershell
python --version    # Should show 3.11.x
pip --version
```

### 2b. Install Node.js 20 LTS

```powershell
winget install OpenJS.NodeJS.LTS
```

Close and reopen PowerShell, then verify:
```powershell
node --version      # v20.x or v22.x
npm --version
```

### 2c. Install PostgreSQL 16

```powershell
# Download from https://www.postgresql.org/download/windows/
# Run installer, set superuser password, keep port 5432
# After install, add to PATH:
$env:Path = "C:\Program Files\PostgreSQL\16\bin;$env:Path"
[Environment]::SetEnvironmentVariable("Path", "C:\Program Files\PostgreSQL\16\bin;" + [Environment]::GetEnvironmentVariable("Path", "Machine"), "Machine")

# Verify:
psql --version
```

### 2d. Install PM2

```powershell
npm install -g pm2 pm2-windows-service pm2-windows-startup
```

### 2e. Install IIS Features

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole, IIS-WebServer, IIS-CommonHttpFeatures, IIS-StaticContent, IIS-DefaultDocument, IIS-DirectoryBrowsing, IIS-HttpErrors, IIS-ApplicationDevelopment, IIS-NetFxExtensibility45, IIS-HealthAndDiagnostics, IIS-HttpLogging, IIS-RequestMonitor, IIS-Security, IIS-RequestFiltering, IIS-Performance, IIS-HttpCompressionStatic, IIS-HttpRedirect, IIS-WebSockets
```

### 2f. Install IIS URL Rewrite & ARR Modules

```powershell
# Install URL Rewrite
winget install Microsoft.IIS.URLRewrite

# Install Application Request Routing (ARR)
# Download manually from: https://www.iis.net/downloads/microsoft/application-request-routing
# Or try:
winget install Microsoft.IIS.ARR
```

> ⚠️ If winget doesn't have ARR, download it from the IIS website and install manually.

### 2g. Open Firewall Ports

```powershell
New-NetFirewallRule -DisplayName "PMS HTTP" -Direction Inbound -Port 80 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "PMS HTTPS" -Direction Inbound -Port 443 -Protocol TCP -Action Allow
# Backend port — needs to be accessible since IIS proxies to 160.226.0.67:8000
New-NetFirewallRule -DisplayName "PMS Backend" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow
# Frontend is only accessed locally by IIS
New-NetFirewallRule -DisplayName "PMS Frontend Internal" -Direction Inbound -Port 3000 -Protocol TCP -Action Allow -LocalAddr 127.0.0.1
```

---

## STEP 3: Set Up PostgreSQL Database

```powershell
# Open psql as the postgres superuser
psql -U postgres

# In the psql prompt, run:
CREATE DATABASE pms_db;
CREATE USER pms_user WITH ENCRYPTED PASSWORD 'YourStrongPassword123!';
GRANT ALL PRIVILEGES ON DATABASE pms_db TO pms_user;
ALTER DATABASE pms_db OWNER TO pms_user;
\q
```

> 🔒 Choose a strong password and save it — you'll need it in Step 4.

---

## STEP 4: Configure Backend Environment

```powershell
cd C:\inetpub\wwwroot\pms-stable\backend
notepad .env
```

Replace the contents with (fill in your actual values):

```ini
# Environment Mode
ENVIRONMENT=production

# Database Configuration
DATABASE_URL=postgresql://pms_user:YourStrongPassword123!@localhost:5432/pms_db

# JWT Configuration — Generate a secure key (see command below)
JWT_SECRET_KEY=PASTE_YOUR_GENERATED_KEY_HERE
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS Settings — Must include your domain
CORS_ALLOWED_ORIGINS=https://pms.nigcomsat.gov.ng,http://localhost:3000
FRONTEND_URL=https://pms.nigcomsat.gov.ng

# SMTP Email Configuration
SMTP_HOST=relay.galaxybackbone.com.ng
SMTP_PORT=1707
SMTP_USERNAME=pmssupport@nigcomsat.gov.ng
SMTP_PASSWORD=YourActualSmtpPassword
SMTP_FROM_EMAIL=pmssupport@nigcomsat.gov.ng
SMTP_FROM_NAME=NIGCOMSAT PMS

# Redis (optional — comment out if not installed)
# REDIS_URL=redis://localhost:6379/0
```

**Generate a JWT secret key** (run this in PowerShell):
```powershell
-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
```
Copy the output and paste it as `JWT_SECRET_KEY`.

---

## STEP 5: Configure Frontend Environment

```powershell
cd C:\inetpub\wwwroot\pms-stable\frontend
notepad .env
```

Set these values:

```ini
# API Configuration — Use your domain with HTTPS
# IMPORTANT: Do NOT include /api — the frontend code appends /api/... automatically
NEXT_PUBLIC_API_URL=https://pms.nigcomsat.gov.ng
NEXT_PUBLIC_WS_URL=wss://pms.nigcomsat.gov.ng

# Environment
NODE_ENV=production
```

> ⚠️ `NEXT_PUBLIC_*` variables are **baked into the build**. You MUST set them before running `npm run build`.

---

## STEP 6: Update Backend CORS & Rate Limiter

The backend already has the updated files in the project. Verify these are in place:

### 6a. `backend/.env` — CORS must include your domain
```
CORS_ALLOWED_ORIGINS=https://pms.nigcomsat.gov.ng,http://localhost:3000
```

### 6b. `backend/utils/limiter.py` — Uses X-Forwarded-For (already updated)
This ensures rate limiting works correctly behind the IIS reverse proxy.

---

## STEP 7: Install Python Dependencies & Run Migrations

```powershell
cd C:\inetpub\wwwroot\pms-stable\backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Deactivate when done
deactivate
```

> If `pip install` fails due to Unicode spacing in `requirements.txt`, fix it:
> ```powershell
> $content = Get-Content requirements.txt -Raw
> $content -replace '[^\x00-\x7F\r\n]', '' | Set-Content requirements.txt -Encoding UTF8
> pip install -r requirements.txt
> ```

---

## STEP 8: Build the Frontend

```powershell
cd C:\inetpub\wwwroot\pms-stable\frontend
npm install
npm run build
```

This will take 2-5 minutes. The built output goes to `.next/` directory.

---

## STEP 9: Configure PM2 Process Manager

### 9a. Backend ecosystem.config.js

```powershell
cd C:\inetpub\wwwroot\pms-stable\backend
notepad ecosystem.config.js
```

Ensure it contains:

```javascript
module.exports = {
  apps: [{
    name: 'pms-backend',
    script: 'main.py',
    interpreter: 'python',
    interpreter: './venv/Scripts/python.exe',
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      PYTHONUNBUFFERED: '1',
      ENVIRONMENT: 'production'
    },
    error_file: './logs/backend-error.log',
    out_file: './logs/backend-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
  }]
};
```

### 9b. Frontend ecosystem.config.js

```powershell
cd C:\inetpub\wwwroot\pms-stable\frontend
notepad ecosystem.config.js
```

Ensure it contains:

```javascript
module.exports = {
  apps: [{
    name: 'pms-frontend',
    script: 'node_modules/next/dist/bin/next',
    args: 'start -p 3000 -H 127.0.0.1',
    interpreter: 'node',
    cwd: 'C:\\inetpub\\wwwroot\\pms-stable\\frontend',
    env: {
      NODE_ENV: 'production',
      NEXT_PUBLIC_API_URL: 'https://pms.nigcomsat.gov.ng',
      NEXT_PUBLIC_WS_URL: 'wss://pms.nigcomsat.gov.ng'
    },
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    error_file: './logs/frontend-error.log',
    out_file: './logs/frontend-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
  }]
};
```

> ⚠️ Set `args: 'start -p 3000 -H 127.0.0.1'` (bind to localhost only, since IIS proxies traffic).

### 9c. Create log directories

```powershell
New-Item -ItemType Directory -Path "C:\inetpub\wwwroot\pms-stable\backend\logs" -Force
New-Item -ItemType Directory -Path "C:\inetpub\wwwroot\pms-stable\frontend\logs" -Force
```

---

## STEP 10: Start Services with PM2

```powershell
# Start backend
cd C:\inetpub\wwwroot\pms-stable\backend
pm2 start ecosystem.config.js

# Start frontend
cd C:\inetpub\wwwroot\pms-stable\frontend
pm2 start ecosystem.config.js

# Save the process list (persists across reboots)
pm2 save

# Check status
pm2 list
```

Verify both services are running:
```powershell
# Backend health check (via public IP)
curl http://160.226.0.67:8000/health
# Expected: {"status":"healthy","service":"NIGCOMSAT PMS API v2.0"}

# Also check via localhost (should work since backend binds to 0.0.0.0)
curl http://localhost:8000/health

# Frontend (via IIS proxy)
curl http://localhost/
```

### 10a. Set PM2 to auto-start on boot

```powershell
pm2-startup install
# Or manually:
pm2-service-install
# Follow prompts — accept defaults
```

---

## STEP 11: Configure IIS Reverse Proxy

### 11a. Enable ARR Proxy

1. Open **IIS Manager** (search for "Internet Information Services")
2. Click on the server name in the left panel
3. Double-click **Application Request Routing Cache**
4. Click **Server Proxy Settings** in the right panel
5. Check **Enable proxy**
6. Set **Response buffer threshold (KB)** to `0` (for streaming)
7. Set **Response timeout (seconds)** to `900` (15 minutes — required for WebSocket keep-alive)
8. Click **Apply** in the right panel

> ⚠️ **The response timeout is critical for WebSocket.** The default ARR timeout (120s) will kill idle WebSocket connections. Set it to at least 900 seconds to match the 30-second client ping interval with plenty of margin.

### 11b. Create the IIS Website

Run the setup script:

```powershell
cd C:\inetpub\wwwroot\pms-stable
.\setup-iis-site.ps1
```

Or manually in IIS Manager:

1. Right-click **Sites** → **Add Website**
2. **Site name**: `PMS-NIGCOMSAT`
3. **Physical path**: `C:\inetpub\wwwroot\pms-stable\frontend`
4. **Binding**: 
   - Type: `http`, IP: `All Unassigned`, Port: `80`
   - Host name: `pms.nigcomsat.gov.ng`
5. Click **OK**

### 11c. Add HTTPS Binding

1. In IIS Manager, select the `PMS-NIGCOMSAT` site
2. Click **Bindings** in the right panel
3. Click **Add**:
   - Type: `https`
   - Port: `443`
   - Host name: `pms.nigcomsat.gov.ng`
   - SSL certificate: Select your certificate (see Step 12)
4. Click **OK**

### 11d. Verify the web.config

The `web.config` file should already be in place at `C:\inetpub\wwwroot\pms-stable\frontend\web.config`. Verify it contains the reverse proxy rules for `/api/*` and WebSocket support.

---

## STEP 12: SSL Certificate

### Option A: Let's Encrypt (Recommended — Free, Auto-renewing)

```powershell
# Install win-acme
winget install win-acme

# Obtain certificate
wacs.exe --target iissite PMS-NIGCOMSAT --installation iis --emailaddress your-email@nigcomsat.gov.ng
```

win-acme will:
- Automatically obtain a certificate from Let's Encrypt
- Bind it to your IIS site
- Set up auto-renewal

### Option B: Government/ISS Certificate

If your organization provides SSL certificates:

```powershell
# Import the .pfx certificate
$cert = Import-PfxCertificate -FilePath "C:\path\to\certificate.pfx" -CertStoreLocation Cert:\LocalMachine\My -Password (ConvertTo-SecureString -String "cert-password" -AsPlainText -Force)

# Bind it to the site
$binding = Get-WebBinding -Name "PMS-NIGCOMSAT" -Protocol "https" -HostHeader "pms.nigcomsat.gov.ng"
$binding.AddSslCertificate($cert.Thumbprint, "My")
```

### Option C: Self-signed (Testing ONLY)

```powershell
# Create self-signed certificate (NOT for production!)
$cert = New-SelfSignedCertificate -DnsName "pms.nigcomsat.gov.ng" -CertStoreLocation "Cert:\LocalMachine\My" -FriendlyName "PMS Test Certificate" -NotAfter (Get-Date).AddYears(1)

# Bind to site
New-WebBinding -Name "PMS-NIGCOMSAT" -Protocol "https" -Port 443 -HostHeader "pms.nigcomsat.gov.ng"
$binding = Get-WebBinding -Name "PMS-NIGCOMSAT" -Protocol "https" -HostHeader "pms.nigcomsat.gov.ng"
$binding.AddSslCertificate($cert.Thumbprint, "My")
```

---

## STEP 13: Final Verification

### 13a. Test internally on the server

```powershell
# Backend
curl http://localhost:8000/health
# Expected: {"status":"healthy","service":"NIGCOMSAT PMS API v2.0"}

# Frontend (via IIS proxy)
curl http://localhost/api/health
# Should proxy to the backend

# Frontend page
curl http://localhost/
# Should return HTML
```

### 13b. Test externally

From your local machine or browser:
```
https://pms.nigcomsat.gov.ng/
```

You should see the PMS login page.

### 13c. Check PM2 logs

```powershell
pm2 logs
# Or specifically:
pm2 logs pms-backend
pm2 logs pms-frontend
```

---

## STEP 14: Security Hardening

### 14a. Restrict port 3000 to localhost only

Since IIS proxies all traffic, port 3000 (Next.js) only needs to be reachable locally:

```powershell
# Port 8000 (backend) must remain accessible — IIS proxies to 160.226.0.67:8000
# If you want to restrict it to only the server itself, use this:
# New-NetFirewallRule -DisplayName "PMS Backend Allow Self" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow -RemoteAddr 160.226.0.67,127.0.0.1
# New-NetFirewallRule -DisplayName "PMS Backend Block Others" -Direction Inbound -Port 8000 -Protocol TCP -Action Block

# Port 3000 (frontend) should only be accessible locally by IIS
New-NetFirewallRule -DisplayName "PMS Frontend Block External" -Direction Inbound -Port 3000 -Protocol TCP -Action Block -RemoteAddr Any
New-NetFirewallRule -DisplayName "PMS Frontend Allow Loopback" -Direction Inbound -Port 3000 -Protocol TCP -Action Allow -RemoteAddr 127.0.0.1
```

### 14b. Change default database password

```powershell
psql -U postgres -c "ALTER USER pms_user WITH PASSWORD 'YourNewVeryStrongPassword!';"
```

Then update `backend/.env` `DATABASE_URL` with the new password and restart:
```powershell
pm2 restart pms-backend
```

### 14c. Rotate the JWT secret

Generate a new one:
```powershell
-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
```

Update `backend/.env` `JWT_SECRET_KEY` and restart:
```powershell
pm2 restart pms-backend
```

> ⚠️ Rotating the JWT secret will invalidate all existing user sessions.

---

## STEP 15: Ongoing Maintenance

### Useful commands

```powershell
# Check service status
pm2 list

# View logs
pm2 logs pms-backend    # Backend logs
pm2 logs pms-frontend   # Frontend logs

# Restart services
pm2 restart pms-backend
pm2 restart pms-frontend
pm2 restart all

# Stop services
pm2 stop all

# IIS management
Start-Website -Name "PMS-NIGCOMSAT"
Stop-Website -Name "PMS-NIGCOMSAT"
Get-Website

# Check IIS logs
Get-Content "C:\inetpub\logs\LogFiles\W3SVC*\*.log" -Tail 50

# Database backup
pg_dump -U postgres -d pms_db -F c -f "C:\backups\pms_db_$(Get-Date -Format 'yyyyMMdd').backup"
```

### Restore database from backup

```powershell
pg_restore -U postgres -d pms_db -1 "C:\backups\pms_db_20250610.backup"
```

---

## Troubleshooting

### Backend won't start
```powershell
cd C:\inetpub\wwwroot\pms-stable\backend
.\venv\Scripts\Activate.ps1
python main.py
# Check the error output
```

### Frontend build fails
```powershell
cd C:\inetpub\wwwroot\pms-stable\frontend
rm -Recurse -Force .next   # Clean build cache
npm run build               # Rebuild
```

### IIS returns 502 Bad Gateway
- Check that PM2 services are running: `pm2 list`
- Check that backend responds: `curl http://160.226.0.67:8000/health`
- Check that frontend responds: `curl http://localhost:3000`
- Check ARR proxy is enabled in IIS Manager

### CORS errors in browser
- Verify `CORS_ALLOWED_ORIGINS` in `backend/.env` includes `https://pms.nigcomsat.gov.ng`
- Restart backend: `pm2 restart pms-backend`

### WebSocket not connecting
- **Check ARR response timeout** — the default 120s timeout kills idle WebSocket connections. Set it to 900s in IIS Manager → Server Proxy Settings
- **Critical**: `web.config` must have `<webSocket enabled="false" />` — when enabled, IIS intercepts WebSocket connections locally and never proxies them to FastAPI via ARR
- Verify ARR proxy is enabled in IIS Manager (Application Request Routing Cache → Server Proxy Settings → Enable proxy)
- The `web.config` has a dedicated WebSocket proxy rule that matches `^api/notifications/ws` with an `{HTTP_UPGRADE}` condition — this ensures ARR handles the `Upgrade: websocket` header correctly
- Check backend logs: `pm2 logs pms-backend` — if WebSocket requests never appear, IIS is not proxying them
- From the server, test WebSocket directly: `wscat -c ws://160.226.0.67:8000/api/notifications/ws?token=YOUR_TOKEN`
- From outside, test through IIS: `wscat -c wss://pms.nigcomsat.gov.ng/api/notifications/ws?token=YOUR_TOKEN`

### SSL certificate issues
- For Let's Encrypt: `wacs.exe --renew`
- Check certificate bindings: `Get-WebBinding -Name "PMS-NIGCOMSAT"`

### Database connection errors
```powershell
# Test connection
psql -U pms_user -d pms_db -h localhost -c "SELECT 1;"
# If this fails, check PostgreSQL is running:
Get-Service postgresql*
```