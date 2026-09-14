param(
    [switch]$SkipManagedImageEngine
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"
$Installer = Join-Path $Root "install.ps1"
$ImageEngineConfig = Join-Path $Root ".ember\image-engine.json"
$ImageEngineInstaller = Join-Path $Root "scripts\install-image-engine.ps1"
$ImageEngineLauncher = Join-Path $Root "scripts\start-image-engine.ps1"

if (-not (Test-Path $Venv) -or -not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "First-run setup is required..." -ForegroundColor Yellow
    & $Installer -SkipImageEngineInstall:$SkipManagedImageEngine
}

$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install -e $Backend

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Push-Location $Frontend
    try { npm ci } finally { Pop-Location }
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Local AI is not installed. Run .\install.ps1 to install Ollama and EmberWriter's recommended writing model." -ForegroundColor Yellow
}

$ImageEnginePid = $null
if (-not $SkipManagedImageEngine) {
    if (-not (Test-Path $ImageEngineConfig)) {
        Write-Host "Managed image engine is not installed yet. Installing Forge..." -ForegroundColor Yellow
        try {
            & $ImageEngineInstaller -Engine forge
        } catch {
            Write-Host "Image-engine installation could not complete: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host "EmberWriter will still open; Visual Canon will show repair guidance." -ForegroundColor Yellow
        }
    }

    if (Test-Path $ImageEngineConfig) {
        try {
            $imageState = & $ImageEngineLauncher -PassThru
            if ($imageState -and $imageState.Started -and $imageState.Pid) {
                $ImageEnginePid = [int]$imageState.Pid
            }
            if ($imageState -and $imageState.BaseUrl) {
                Write-Host "Image engine:    $($imageState.BaseUrl)"
            }
        } catch {
            Write-Host "Managed image engine could not start: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host "EmberWriter will still open; use the image-server status control for diagnostics." -ForegroundColor Yellow
        }
    }
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
    if ($ImageEnginePid) {
        try {
            & taskkill.exe /PID $ImageEnginePid /T /F 2>$null | Out-Null
        } catch { }
    }
}
