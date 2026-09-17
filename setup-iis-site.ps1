# =============================================================================
# IIS Site Setup Script for pms.nigcomsat.gov.ng
# =============================================================================
# Run this script as Administrator on the target Windows Server 2022.
# =============================================================================

param(
    [string]$Domain = "pms.nigcomsat.gov.ng",
    [string]$SiteName = "PMS-NIGCOMSAT",
    [string]$SitePath = "C:\inetpub\wwwroot\pms-stable\frontend",
    [int]$FrontendPort = 3000,
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  IIS Site Setup for $Domain" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# --- STEP 1: Ensure IIS features are installed ---
Write-Host ""
Write-Host "[1/7] Checking IIS features..." -ForegroundColor Yellow

$iisFeatures = @(
    "IIS-WebServerRole",
    "IIS-WebServer",
    "IIS-CommonHttpFeatures",
    "IIS-StaticContent",
    "IIS-DefaultDocument",
    "IIS-DirectoryBrowsing",
    "IIS-HttpErrors",
    "IIS-ApplicationDevelopment",
    "IIS-NetFxExtensibility45",
    "IIS-HealthAndDiagnostics",
    "IIS-HttpLogging",
    "IIS-RequestMonitor",
    "IIS-Security",
    "IIS-RequestFiltering",
    "IIS-Performance",
    "IIS-HttpCompressionStatic",
    "IIS-WebSockets",
    "IIS-HttpRedirect",
    "IIS-ApplicationRequestRouting",
    "IIS-UrlRewrite"
)

foreach ($feature in $iisFeatures) {
    $installed = Get-WindowsOptionalFeature -Online -FeatureName $feature -ErrorAction SilentlyContinue
    if ($installed -and $installed.State -eq "Enabled") {
        Write-Host "  [OK] $feature already enabled" -ForegroundColor Green
    } else {
        Write-Host "  Installing $feature..." -ForegroundColor Gray
        Enable-WindowsOptionalFeature -Online -FeatureName $feature -NoRestart | Out-Null
    }
}

# --- STEP 2: Check URL Rewrite and ARR modules ---
Write-Host ""
Write-Host "[2/7] Checking IIS modules..." -ForegroundColor Yellow

$rewriteModule = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\IIS Extensions\URL Rewrite\*" -ErrorAction SilentlyContinue
if (-not $rewriteModule) {
    Write-Host "  URL Rewrite module not found." -ForegroundColor Red
    Write-Host "  Install it with: winget install Microsoft.IIS.URLRewrite" -ForegroundColor Gray
    $wingetAvailable = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetAvailable) {
        Write-Host "  Attempting winget install..." -ForegroundColor Gray
        winget install Microsoft.IIS.URLRewrite --accept-package-agreements --accept-source-agreements
    }
} else {
    Write-Host "  [OK] URL Rewrite module found" -ForegroundColor Green
}

$arrModule = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\IIS Extensions\Application Request Routing\*" -ErrorAction SilentlyContinue
if (-not $arrModule) {
    Write-Host "  ARR module not found." -ForegroundColor Red
    Write-Host "  Download from: https://www.iis.net/downloads/microsoft/application-request-routing" -ForegroundColor Gray
    Write-Host "  After installing, enable proxy in IIS Manager and re-run this script." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] ARR module found" -ForegroundColor Green
}

# --- STEP 3: Enable ARR proxy ---
Write-Host ""
Write-Host "[3/7] Enabling ARR proxy..." -ForegroundColor Yellow

try {
    Import-Module WebAdministration
    Set-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" -Filter "system.webServer/proxy" -Name "enabled" -Value "true" -ErrorAction SilentlyContinue
    Write-Host "  [OK] ARR proxy enabled" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] Could not enable ARR proxy automatically." -ForegroundColor Yellow
    Write-Host "  Open IIS Manager > Application Request Routing Cache > Server Proxy Settings > Enable proxy" -ForegroundColor Yellow
}

# --- STEP 4: Create IIS site directory and web.config ---
Write-Host ""
Write-Host "[4/7] Setting up site directory..." -ForegroundColor Yellow

if (-not (Test-Path "$SitePath\web.config")) {
    Write-Host "  web.config not found at $SitePath" -ForegroundColor Yellow
    Write-Host "  Creating web.config with reverse proxy rules..." -ForegroundColor Gray

    $webConfigContent = @"
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <!--
      WebSocket must be DISABLED so IIS does NOT intercept WebSocket upgrade
      requests locally.  When enabled, IIS's own module grabs the connection
      before ARR can proxy it to FastAPI, causing instant failures.
      With it disabled, ARR detects the Upgrade: websocket header and proxies
      the persistent connection to the backend automatically.
    -->
    <webSocket enabled="false" />
    <rewrite>
      <outboundRules>
        <rule name="Rewrite Location Header" preCondition="IsRedirect" enabled="true">
          <match serverVariable="RESPONSE_Location" pattern="^http://([^/]*)(/(.*))?" />
          <action type="Rewrite" value="https://{R:1}/{R:3}" />
        </rule>
        <preConditions>
          <preCondition name="IsRedirect">
            <add input="{RESPONSE_STATUS}" pattern="3[0-9]{2}" />
          </preCondition>
        </preConditions>
      </outboundRules>
      <rules>
        <!--
          All /api/* requests (including WebSocket upgrades) proxy to FastAPI backend.
          ARR automatically upgrades the connection when it detects the
          Upgrade: websocket header, so a separate ws:// rule is NOT needed.
        -->
        <rule name="API and WebSocket Proxy" stopProcessing="true">
          <match url="^api/(.*)" />
          <action type="Rewrite" url="http://160.226.0.67:8000/api/{R:1}" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_PROTO" value="https" />
            <set name="HTTP_X_FORWARDED_HOST" value="{HTTP_HOST}" />
          </serverVariables>
        </rule>
        <rule name="NextJS Proxy" stopProcessing="true">
          <match url=".*" />
          <action type="Rewrite" url="http://localhost:3000/{R:0}" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
"@
    Set-Content -Path "$SitePath\web.config" -Value $webConfigContent -Encoding UTF8
    Write-Host "  [OK] web.config created" -ForegroundColor Green
} else {
    Write-Host "  [OK] web.config already exists at $SitePath" -ForegroundColor Green
}

# --- STEP 5: Create IIS site ---
Write-Host ""
Write-Host "[5/7] Creating IIS site..." -ForegroundColor Yellow

Import-Module WebAdministration

# Remove existing site if it exists
$existingSite = Get-Website -Name $SiteName -ErrorAction SilentlyContinue
if ($existingSite) {
    Write-Host "  Removing existing site '$SiteName'..." -ForegroundColor Gray
    Remove-Website -Name $SiteName
}

# Create the site with HTTP binding first
New-Website -Name $SiteName -PhysicalPath $SitePath -Port 80 -HostHeader $Domain -Force | Out-Null
Write-Host "  [OK] Site created with HTTP binding on port 80" -ForegroundColor Green

# Add binding for www subdomain
New-WebBinding -Name $SiteName -Protocol "http" -Port 80 -HostHeader "www.$Domain"
Write-Host "  [OK] Added HTTP binding for www.$Domain" -ForegroundColor Green

# Set the application pool
$appPool = "PMSAppPool"
if (-not (Get-IISAppPool -Name $appPool -ErrorAction SilentlyContinue)) {
    New-IISAppPool -Name $appPool -Force
}
Set-ItemProperty "IIS:\Sites\$SiteName" -Name applicationPool -Value $appPool
Set-ItemProperty "IIS:\AppPools\$appPool" -Name processModel.identityType -Value 0
Write-Host "  [OK] Application pool '$appPool' configured" -ForegroundColor Green

# --- STEP 6: SSL Certificate ---
Write-Host ""
Write-Host "[6/7] Setting up SSL..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  You have 3 options for the SSL certificate:" -ForegroundColor White
Write-Host ""
Write-Host "  OPTION A: Let's Encrypt (free, auto-renewing)" -ForegroundColor Cyan
Write-Host "    - Install win-acme: winget install win-acme" -ForegroundColor Gray
Write-Host "    - Then run: wacs.exe --target iissite $SiteName" -ForegroundColor Gray
Write-Host ""
Write-Host "  OPTION B: Import an existing .pfx certificate" -ForegroundColor Cyan
Write-Host "    - You must have a .pfx file from your CA" -ForegroundColor Gray
Write-Host ""
Write-Host "  OPTION C: Self-signed (for testing ONLY)" -ForegroundColor Cyan
Write-Host "    - Not recommended for production" -ForegroundColor Gray
Write-Host ""

$certChoice = Read-Host "  Choose certificate option (A/B/C)"

switch ($certChoice.ToUpper()) {
    "A" {
        Write-Host ""
        Write-Host "  Setting up win-acme for Let's Encrypt..." -ForegroundColor Yellow
        $wacsPath = Get-Command wacs.exe -ErrorAction SilentlyContinue
        if (-not $wacsPath) {
            Write-Host "  Installing win-acme via winget..." -ForegroundColor Gray
            winget install win-acme --accept-package-agreements --accept-source-agreements
        }
        Write-Host ""
        Write-Host "  Run this command to obtain a certificate:" -ForegroundColor White
        Write-Host "  wacs.exe --target iissite $SiteName --installation iis" -ForegroundColor Green
        Write-Host ""
        Write-Host "  [!] DNS must already point $Domain to this server IP." -ForegroundColor Yellow
        Write-Host "  [!] Port 80 must be accessible from the internet." -ForegroundColor Yellow
    }

    "B" {
        $pfxPath = Read-Host "  Enter path to .pfx certificate file"
        $pfxPassword = Read-Host "  Enter certificate password" -AsSecureString
        $cert = Import-PfxCertificate -FilePath $pfxPath -CertStoreLocation Cert:\LocalMachine\My -Password $pfxPassword
        Write-Host "  [OK] Certificate imported. Thumbprint: $($cert.Thumbprint)" -ForegroundColor Green

        New-WebBinding -Name $SiteName -Protocol "https" -Port 443 -HostHeader $Domain -SslFlags 1
        New-WebBinding -Name $SiteName -Protocol "https" -Port 443 -HostHeader "www.$Domain" -SslFlags 1

        $binding = Get-WebBinding -Name $SiteName -Protocol "https" -HostHeader $Domain
        $binding.AddSslCertificate($cert.Thumbprint, "My")

        $bindingWww = Get-WebBinding -Name $SiteName -Protocol "https" -HostHeader "www.$Domain"
        $bindingWww.AddSslCertificate($cert.Thumbprint, "My")

        Write-Host "  [OK] HTTPS binding configured" -ForegroundColor Green
    }

    "C" {
        Write-Host "  Creating self-signed certificate (TESTING ONLY)..." -ForegroundColor Yellow
        $cert = New-SelfSignedCertificate -DnsName $Domain, "www.$Domain" -CertStoreLocation "Cert:\LocalMachine\My" -FriendlyName "PMS Test Certificate" -NotAfter (Get-Date).AddYears(1)
        Write-Host "  [OK] Self-signed certificate created. Thumbprint: $($cert.Thumbprint)" -ForegroundColor Green

        New-WebBinding -Name $SiteName -Protocol "https" -Port 443 -HostHeader $Domain
        New-WebBinding -Name $SiteName -Protocol "https" -Port 443 -HostHeader "www.$Domain"

        $binding = Get-WebBinding -Name $SiteName -Protocol "https" -HostHeader $Domain
        $binding.AddSslCertificate($cert.Thumbprint, "My")

        $bindingWww = Get-WebBinding -Name $SiteName -Protocol "https" -HostHeader "www.$Domain"
        $bindingWww.AddSslCertificate($cert.Thumbprint, "My")

        Write-Host "  [OK] HTTPS binding configured" -ForegroundColor Green
        Write-Host "  [!] WARNING: Self-signed certificates will show security warnings!" -ForegroundColor Red
    }
}

# --- STEP 7: Configure HTTP to HTTPS redirect ---
Write-Host ""
Write-Host "[7/7] Configuring HTTP to HTTPS redirect..." -ForegroundColor Yellow

$webConfigPath = "$SitePath\web.config"
[xml]$webConfig = Get-Content $webConfigPath

$existingRedirect = $webConfig.SelectSingleNode("//rule[@name='HTTP to HTTPS Redirect']")
if (-not $existingRedirect) {
    $rulesNode = $webConfig.SelectSingleNode("//rules")

    $redirectRule = $webConfig.CreateElement("rule")
    $redirectRule.SetAttribute("name", "HTTP to HTTPS Redirect")
    $redirectRule.SetAttribute("stopProcessing", "true")

    $match = $webConfig.CreateElement("match")
    $match.SetAttribute("url", "(.*)")
    $redirectRule.AppendChild($match)

    $conditions = $webConfig.CreateElement("conditions")
    $add = $webConfig.CreateElement("add")
    $add.SetAttribute("input", "{HTTPS}")
    $add.SetAttribute("pattern", "^OFF$")
    $conditions.AppendChild($add)
    $redirectRule.AppendChild($conditions)

    $action = $webConfig.CreateElement("action")
    $action.SetAttribute("type", "Redirect")
    $action.SetAttribute("url", "https://{HTTP_HOST}/{R:1}")
    $action.SetAttribute("redirectType", "Permanent")
    $redirectRule.AppendChild($action)

    $rulesNode.PrependChild($redirectRule)
    $webConfig.Save($webConfigPath)
    Write-Host "  [OK] HTTP to HTTPS redirect added to web.config" -ForegroundColor Green
} else {
    Write-Host "  [OK] HTTPS redirect already configured" -ForegroundColor Green
}

# --- Final ---
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  IIS Setup Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Make sure DNS for $Domain points to this server IP" -ForegroundColor Gray
Write-Host "  2. Start the IIS site:" -ForegroundColor Gray
Write-Host "     Start-Website -Name '$SiteName'" -ForegroundColor Gray
Write-Host "  3. Open firewall for ports 80 and 443:" -ForegroundColor Gray
Write-Host "     New-NetFirewallRule -DisplayName 'PMS HTTPS' -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow" -ForegroundColor Gray
Write-Host "     New-NetFirewallRule -DisplayName 'PMS HTTP' -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow" -ForegroundColor Gray
Write-Host ""
Write-Host "  Verify: Open https://$Domain in a browser" -ForegroundColor Green
Write-Host ""