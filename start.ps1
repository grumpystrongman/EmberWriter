param(
    [switch]$SkipManagedImageEngine,
    [string]$DataDir = ""
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
$RuntimeDir = Join-Path $Root ".ember"
$LogDir = Join-Path $RuntimeDir "logs"
$BackendOutLog = Join-Path $LogDir "backend.out.log"
$BackendErrLog = Join-Path $LogDir "backend.err.log"
$FrontendOutLog = Join-Path $LogDir "frontend.out.log"
$FrontendErrLog = Join-Path $LogDir "frontend.err.log"
$FrontendNodeModules = Join-Path $Frontend "node_modules"
$FrontendViteCmd = Join-Path $Frontend "node_modules\.bin\vite.cmd"
$ApiUrl = "http://127.0.0.1:8000/api/health"
$UiUrl = "http://127.0.0.1:5173"

function Test-ProjectDataRoot([string]$DataRoot) {
    if (-not $DataRoot) { return $false }
    $projects = Join-Path $DataRoot "projects"
    if (-not (Test-Path $projects)) { return $false }
    $projectFile = Get-ChildItem -Path $projects -Filter "project.json" -File -Recurse -Depth 2 -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $projectFile
}

function Test-EmberApi {
    try {
        $payload = Invoke-RestMethod -Uri $ApiUrl -Method Get -TimeoutSec 2
        return ($payload.ok -eq $true -and $payload.service -eq "EmberWriter")
    } catch {
        return $false
    }
}

function Test-EmberUi {
    try {
        $response = Invoke-WebRequest -Uri $UiUrl -Method Get -TimeoutSec 2 -UseBasicParsing
        return ($response.StatusCode -eq 200 -and $response.Content -match "EmberWriter")
    } catch {
        return $false
    }
}

function Get-ListenerProcessId([int]$Port) {
    try {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        if ($listener) { return [int]$listener.OwningProcess }
    } catch {
        return $null
    }
    return $null
}

function Stop-ExistingEmberService([int]$Port, [scriptblock]$HealthCheck, [string]$Label) {
    $healthy = & $HealthCheck
    $listenerPid = Get-ListenerProcessId $Port

    if ($healthy) {
        if ($listenerPid -and $listenerPid -ne $PID) {
            Write-Host "Stopping stale $Label process on port $Port (PID $listenerPid)..." -ForegroundColor Yellow
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
            for ($attempt = 0; $attempt -lt 20; $attempt++) {
                Start-Sleep -Milliseconds 250
                if (-not (Get-ListenerProcessId $Port)) { return }
            }
            throw "$Label on port $Port did not stop cleanly. Close the older EmberWriter launch and run start.ps1 again."
        }
        throw "$Label is already running on port $Port, but EmberWriter could not determine its process ID. Close the older EmberWriter launch and run start.ps1 again."
    }

    if ($listenerPid) {
        throw "Port $Port is already in use by another process (PID $listenerPid). EmberWriter will not open against the wrong service."
    }
}

function Stop-FrontendNodeProcesses {
    try {
        $frontendPath = [System.IO.Path]::GetFullPath($Frontend)
        $processes = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -and $_.CommandLine.IndexOf($frontendPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        }

        $stoppedAny = $false
        foreach ($process in $processes) {
            $processId = [int]$process.ProcessId
            if ($processId -and $processId -ne $PID) {
                Write-Host "Stopping stale EmberWriter frontend Node process (PID $processId)..." -ForegroundColor Yellow
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                $stoppedAny = $true
            }
        }

        if ($stoppedAny) {
            Start-Sleep -Milliseconds 750
        }
    } catch {
        Write-Host "Could not inspect stale frontend Node processes: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Wait-ForService([System.Diagnostics.Process]$Process, [scriptblock]$HealthCheck, [int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) { return $false }
        if (& $HealthCheck) { return $true }
        Start-Sleep -Milliseconds 300
    }
    return $false
}

function Show-LogTail([string]$Path, [string]$Label) {
    if (-not (Test-Path $Path)) { return }
    Write-Host ""
    Write-Host "$Label ($Path):" -ForegroundColor Yellow
    Get-Content -Path $Path -Tail 80 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
}

function Test-FrontendDependencies([string]$NpmPath) {
    if (-not (Test-Path $FrontendNodeModules)) { return $false }
    if (-not (Test-Path $FrontendViteCmd)) { return $false }

    Push-Location $Frontend
    try {
        & $NpmPath ls --depth=0 --include=dev --silent *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        Pop-Location
    }
}

function Repair-FrontendDependencies([string]$NpmPath) {
    Write-Host "Frontend dependencies are missing or incomplete. Repairing with npm ci..." -ForegroundColor Yellow
    Push-Location $Frontend
    try {
        $maxAttempts = 3
        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            & $NpmPath ci --include=dev
            if ($LASTEXITCODE -eq 0) { break }

            if ($attempt -lt $maxAttempts) {
                Write-Host "npm ci failed (attempt $attempt of $maxAttempts). Retrying after Windows releases file handles..." -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            }
        }

        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed while repairing EmberWriter frontend dependencies."
        }
    } finally {
        Pop-Location
    }

    if (-not (Test-Path $FrontendViteCmd)) {
        throw "Frontend dependency repair completed but Vite is still missing at $FrontendViteCmd."
    }
    if (-not (Test-FrontendDependencies $NpmPath)) {
        throw "Frontend dependency repair completed but npm still reports an incomplete dependency tree."
    }
    Write-Host "Frontend dependencies repaired; Vite is available." -ForegroundColor Green
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Remove-Item $BackendOutLog, $BackendErrLog, $FrontendOutLog, $FrontendErrLog -Force -ErrorAction SilentlyContinue

if ($DataDir) {
    $env:EMBER_DATA_DIR = [System.IO.Path]::GetFullPath((Join-Path $LaunchDirectory $DataDir))
} else {
    $legacyDataRoot = Join-Path $LaunchDirectory "data"
    $defaultResolved = [System.IO.Path]::GetFullPath($DefaultDataRoot)
    $legacyResolved = [System.IO.Path]::GetFullPath($legacyDataRoot)
    $configuredDataRoot = $env:EMBER_DATA_DIR

    # A prior shell can retain an old EMBER_DATA_DIR. If this checkout already
    # contains real projects, prefer the checkout's data root automatically.
    if (Test-ProjectDataRoot $DefaultDataRoot) {
        if ($configuredDataRoot) {
            try {
                $configuredResolved = [System.IO.Path]::GetFullPath($configuredDataRoot)
            } catch {
                $configuredResolved = $configuredDataRoot
            }
            if ($configuredResolved -ne $defaultResolved) {
                Write-Host "Using projects found in this EmberWriter checkout instead of stale EMBER_DATA_DIR: $configuredDataRoot" -ForegroundColor Yellow
            }
        }
        $env:EMBER_DATA_DIR = $DefaultDataRoot
    } elseif ($configuredDataRoot -and (Test-ProjectDataRoot $configuredDataRoot)) {
        $env:EMBER_DATA_DIR = [System.IO.Path]::GetFullPath($configuredDataRoot)
    } elseif ($legacyResolved -ne $defaultResolved -and (Test-ProjectDataRoot $legacyDataRoot)) {
        $env:EMBER_DATA_DIR = $legacyDataRoot
        Write-Host "Recovered existing EmberWriter projects from legacy data location: $legacyDataRoot" -ForegroundColor Green
    } else {
        $env:EMBER_DATA_DIR = $DefaultDataRoot
    }
}

Write-Host "Project data:    $env:EMBER_DATA_DIR"

if (-not (Test-Path $Venv)) {
    Write-Host "First-run backend setup is required..." -ForegroundColor Yellow
    & $Installer -SkipImageEngineInstall:$SkipManagedImageEngine
}

$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "EmberWriter's Python environment is incomplete at $Venv. Rerun install.ps1."
}
& $Python -m pip install -e $Backend

$Npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $Npm) { $Npm = (Get-Command npm -ErrorAction SilentlyContinue).Source }
if (-not $Npm) {
    throw "npm was not found. Install current Node.js LTS, then run start.ps1 again."
}

# Stop the old EmberWriter frontend before npm inspects or replaces node_modules.
# Vite/Node commonly keeps package files open on Windows and can make npm ci fail
# with EPERM if dependency repair runs first.
Stop-ExistingEmberService -Port 5173 -HealthCheck ${function:Test-EmberUi} -Label "EmberWriter UI"
Stop-FrontendNodeProcesses

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
                if ($imageState.Ready) {
                    Write-Host "Image engine:    ready at $($imageState.BaseUrl)" -ForegroundColor Green
                } else {
                    Write-Host "Image engine:    starting at $($imageState.BaseUrl)" -ForegroundColor Cyan
                }
            }
        } catch {
            Write-Host "Managed image engine could not start: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host "EmberWriter will still open; use the image-server status control for diagnostics." -ForegroundColor Yellow
        }
    }
}

if (-not (Test-FrontendDependencies $Npm)) {
    Stop-FrontendNodeProcesses
    Repair-FrontendDependencies $Npm
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Local AI is not installed. Run .\install.ps1 to install Ollama and EmberWriter's recommended writing model." -ForegroundColor Yellow
}

$BackendProcess = $null
$FrontendProcess = $null

try {
    # Never silently reuse stale dev processes. They are a common reason the UI
    # appears current while its API is gone or running older code.
    Stop-ExistingEmberService -Port 8000 -HealthCheck ${function:Test-EmberApi} -Label "EmberWriter API"

    $BackendProcess = Start-Process -FilePath $Python -ArgumentList @(
        "-m", "uvicorn", "app.main:app",
        "--app-dir", $Backend,
        "--host", "127.0.0.1",
        "--port", "8000"
    ) -WorkingDirectory $Root -RedirectStandardOutput $BackendOutLog -RedirectStandardError $BackendErrLog -PassThru

    if (-not (Wait-ForService -Process $BackendProcess -HealthCheck ${function:Test-EmberApi} -TimeoutSeconds 30)) {
        Show-LogTail $BackendOutLog "Backend output"
        Show-LogTail $BackendErrLog "Backend error"
        throw "EmberWriter API failed to become healthy on port 8000. The browser was not opened. See the backend logs above."
    }

    Write-Host "EmberWriter API: healthy at http://127.0.0.1:8000" -ForegroundColor Green

    # Check again in case another process claimed the UI port while dependencies
    # were being repaired or the managed image engine was starting.
    Stop-ExistingEmberService -Port 5173 -HealthCheck ${function:Test-EmberUi} -Label "EmberWriter UI"

    $FrontendProcess = Start-Process -FilePath $Npm -ArgumentList @("run", "dev", "--prefix", $Frontend) -WorkingDirectory $Root -RedirectStandardOutput $FrontendOutLog -RedirectStandardError $FrontendErrLog -PassThru

    if (-not (Wait-ForService -Process $FrontendProcess -HealthCheck ${function:Test-EmberUi} -TimeoutSeconds 30)) {
        Show-LogTail $FrontendOutLog "Frontend output"
        Show-LogTail $FrontendErrLog "Frontend error"
        throw "EmberWriter UI failed to become healthy on port 5173. The browser was not opened."
    }

    Write-Host "EmberWriter UI:  healthy at $UiUrl" -ForegroundColor Green
    Start-Process $UiUrl
    Wait-Process -Id $FrontendProcess.Id
}
finally {
    if ($BackendProcess -and -not $BackendProcess.HasExited) { Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue }
    if ($FrontendProcess -and -not $FrontendProcess.HasExited) { Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue }
    if ($ImageEnginePid) {
        try {
            & taskkill.exe /PID $ImageEnginePid /T /F 2>$null | Out-Null
        } catch { }
    }
}
