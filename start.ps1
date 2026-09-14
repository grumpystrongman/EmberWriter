param(
    [switch]$SkipManagedImageEngine
)

$ErrorActionPreference = "Stop"

$LaunchDirectory = (Get-Location).Path
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"
$Installer = Join-Path $Root "install.ps1"
$ImageEngineConfig = Join-Path $Root ".ember\image-engine.json"
$ImageEngineInstaller = Join-Path $Root "scripts\install-image-engine.ps1"
$ImageEngineLauncher = Join-Path $Root "scripts\start-image-engine.ps1"
$DefaultDataRoot = Join-Path $Root "data"

function Test-ProjectDataRoot([string]$DataRoot) {
    if (-not $DataRoot) { return $false }
    $projects = Join-Path $DataRoot "projects"
    if (-not (Test-Path $projects)) { return $false }
    $projectFile = Get-ChildItem -Path $projects -Filter "project.json" -File -Recurse -Depth 2 -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $projectFile
}

if (-not $env:EMBER_DATA_DIR) {
    $legacyDataRoot = Join-Path $LaunchDirectory "data"
    $defaultResolved = [System.IO.Path]::GetFullPath($DefaultDataRoot)
    $legacyResolved = [System.IO.Path]::GetFullPath($legacyDataRoot)

    if (Test-ProjectDataRoot $DefaultDataRoot) {
        $env:EMBER_DATA_DIR = $DefaultDataRoot
    } elseif ($legacyResolved -ne $defaultResolved -and (Test-ProjectDataRoot $legacyDataRoot)) {
        $env:EMBER_DATA_DIR = $legacyDataRoot
        Write-Host "Recovered existing EmberWriter projects from legacy data location: $legacyDataRoot" -ForegroundColor Green
    } else {
        $env:EMBER_DATA_DIR = $DefaultDataRoot
    }
}

Write-Host "Project data:    $env:EMBER_DATA_DIR"

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
) -WorkingDirectory $Root -PassThru

$Npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $Npm) { $Npm = (Get-Command npm).Source }
$FrontendProcess = Start-Process -FilePath $Npm -ArgumentList @("run", "dev", "--prefix", $Frontend) -WorkingDirectory $Root -PassThru

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
