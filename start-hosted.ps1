param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9-]+$')]
    [string]$FirebaseProjectId
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv"
$Installer = Join-Path $Root "install.ps1"
$HostedUrl = "https://$FirebaseProjectId.web.app"

if (-not (Test-Path $Venv)) {
    Write-Host "First-run setup is required..." -ForegroundColor Yellow
    & $Installer
}

$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install -e $Backend

$env:EMBER_CORS_ORIGINS = "https://$FirebaseProjectId.web.app,https://$FirebaseProjectId.firebaseapp.com"

Write-Host "EmberWriter hosted UI: $HostedUrl" -ForegroundColor Green
Write-Host "EmberWriter local API: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Your manuscripts and SQLite data remain under the local data directory." -ForegroundColor Cyan
Write-Host "Keep this window open while using the hosted UI. Press Ctrl+C to stop the API." -ForegroundColor Yellow

Start-Process $HostedUrl
& $Python -m uvicorn app.main:app --app-dir $Backend --host 127.0.0.1 --port 8000
