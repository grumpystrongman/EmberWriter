$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"

if (-not (Test-Path $Venv)) {
    Write-Host "Creating Python environment..."
    py -3.11 -m venv $Venv
}

$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install -e $Backend

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Push-Location $Frontend
    try { npm install } finally { Pop-Location }
}

$BackendProcess = Start-Process -FilePath $Python -ArgumentList @(
    "-m", "uvicorn", "app.main:app",
    "--app-dir", $Backend,
    "--host", "127.0.0.1",
    "--port", "8000"
) -PassThru

$Npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $Npm) { $Npm = (Get-Command npm).Source }
$FrontendProcess = Start-Process -FilePath $Npm -ArgumentList @("run", "dev", "--prefix", $Frontend) -PassThru

Write-Host "EmberWriter API: http://127.0.0.1:8000"
Write-Host "EmberWriter UI:  http://127.0.0.1:5173"
Start-Process "http://127.0.0.1:5173"

try {
    Wait-Process -Id $FrontendProcess.Id
}
finally {
    if (-not $BackendProcess.HasExited) { Stop-Process -Id $BackendProcess.Id }
    if (-not $FrontendProcess.HasExited) { Stop-Process -Id $FrontendProcess.Id }
}
