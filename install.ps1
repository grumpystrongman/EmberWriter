param(
    [ValidateSet("auto", "8b", "12b", "14b", "24b")]
    [string]$AdultModelTier = "auto",
    [switch]$SkipModelDownload,
    [ValidateSet("forge", "automatic1111")]
    [string]$ImageEngine = "forge",
    [switch]$SkipImageEngineInstall,
    [switch]$SkipImageModelDownload
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"
$FrontendViteCmd = Join-Path $Frontend "node_modules\.bin\vite.cmd"

# EmberWriter is a fiction-writing application, so setup installs a creative/RP model that is
# explicitly capable of the author's requested adult prose. The old Qwen Heretic models remain
# usable if already installed, but they are no longer the managed writing dependency.
$AdultBaseline = "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"
$AdultHighHeat = "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"
$HighHeatMinimumFreeGb = 22

function Require-Command([string]$Name, [string]$Message) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw $Message
    }
}

function Get-FreeDiskGb([string]$Path) {
    $rootPath = [System.IO.Path]::GetPathRoot((Resolve-Path $Path).Path)
    $drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($rootPath.TrimEnd('\'))'"
    if (-not $drive) { return 0 }
    return [math]::Floor($drive.FreeSpace / 1GB)
}

function Stop-FrontendBuildProcesses {
    # Vite launches esbuild as a child process. On Windows either process can retain an open
    # handle to node_modules\@esbuild\...\esbuild.exe, which makes npm ci fail with EPERM while
    # replacing the dependency tree. Stop only processes whose executable/command line belongs
    # to this EmberWriter frontend; do not kill unrelated Node applications on the machine.
    try {
        $frontendPath = [System.IO.Path]::GetFullPath($Frontend)
        $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -in @("node.exe", "esbuild.exe") -and (
                ($_.ExecutablePath -and $_.ExecutablePath.IndexOf($frontendPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) -or
                ($_.CommandLine -and $_.CommandLine.IndexOf($frontendPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
            )
        }

        $stoppedAny = $false
        foreach ($process in $processes) {
            $processId = [int]$process.ProcessId
            if (-not $processId -or $processId -eq $PID) { continue }

            Write-Host "Stopping running EmberWriter frontend process $($process.Name) (PID $processId) before dependency install..." -ForegroundColor Yellow
            if (Get-Command taskkill.exe -ErrorAction SilentlyContinue) {
                & taskkill.exe /PID $processId /T /F *> $null
            } else {
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
            $stoppedAny = $true
        }

        if ($stoppedAny) {
            Start-Sleep -Milliseconds 1000
        }
    } catch {
        Write-Host "Could not fully inspect running frontend processes: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Install-FrontendDependencies {
    Stop-FrontendBuildProcesses
    Push-Location $Frontend
    try {
        $maxAttempts = 3
        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            npm ci --include=dev
            if ($LASTEXITCODE -eq 0) { return }

            if ($attempt -lt $maxAttempts) {
                Write-Host "npm ci failed (attempt $attempt of $maxAttempts). Releasing EmberWriter/Vite/esbuild file handles and retrying..." -ForegroundColor Yellow
                Stop-FrontendBuildProcesses
                Start-Sleep -Seconds 2
            }
        }

        throw "npm ci failed while installing EmberWriter frontend dependencies after $maxAttempts attempts. Close any remaining EmberWriter/Vite terminal or browser-launched dev process and rerun install.ps1."
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "EmberWriter setup" -ForegroundColor Cyan
Write-Host "===============`n"

Require-Command "py" "Python 3.11 is required. Install Python 3.11, then run install.ps1 again."
Require-Command "npm" "Node.js/npm is required. Install current Node.js LTS, then run install.ps1 again."

if (-not (Test-Path $Venv)) {
    Write-Host "Creating Python 3.11 environment..."
    py -3.11 -m venv $Venv
}
$Python = Join-Path $Venv "Scripts\python.exe"
Write-Host "Installing EmberWriter backend..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -e $Backend

Write-Host "Installing locked frontend dependencies (including Vite)..."
Install-FrontendDependencies
if (-not (Test-Path $FrontendViteCmd)) {
    throw "Frontend setup completed without node_modules\.bin\vite.cmd. Delete frontend\node_modules and rerun install.ps1."
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama is not installed. Attempting Windows installation..." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --exact --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        throw "Ollama is required for local AI. Install Ollama from ollama.com, then rerun install.ps1."
    }
}

Require-Command "ollama" "Ollama was installed but is not yet available in this terminal. Open a new PowerShell window and rerun install.ps1."

if (-not $SkipModelDownload) {
    $totalRamGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    $freeDiskGb = Get-FreeDiskGb $Root
    $chosen = $AdultBaseline

    # Keep the legacy 8b/14b switches accepted so existing setup commands do not break. Both now
    # map to the stronger 12B creative baseline rather than reinstalling the old Qwen stack.
    $highHeatRequested = $AdultModelTier -eq "24b"
    $highHeatAuto = $AdultModelTier -eq "auto" -and $totalRamGb -ge 32 -and $freeDiskGb -ge $HighHeatMinimumFreeGb
    if ($highHeatRequested) {
        if ($freeDiskGb -lt $HighHeatMinimumFreeGb) {
            throw "The 24B high-heat model needs at least ${HighHeatMinimumFreeGb} GB free. Only ${freeDiskGb} GB is available."
        }
        $chosen = $AdultHighHeat
    } elseif ($highHeatAuto) {
        $chosen = $AdultHighHeat
    }

    Write-Host ""
    Write-Host "Managed EmberWriter fiction model: $chosen" -ForegroundColor Green
    Write-Host "System RAM detected: ${totalRamGb} GB"
    Write-Host "Free disk detected: ${freeDiskGb} GB"
    Write-Host "Downloading model if needed. This can take several minutes..."
    & ollama pull $chosen
    if ($LASTEXITCODE -ne 0) {
        throw "Ollama failed to download the managed writing model: $chosen"
    }

    $installedModels = @(& ollama list | Select-Object -Skip 1 | ForEach-Object { ($_ -split '\s+')[0] })
    if (-not ($installedModels | Where-Object { $_ -ieq $chosen })) {
        throw "Ollama reported a successful pull, but the managed writing model is not installed: $chosen"
    }

    $ConfigDir = Join-Path $Root ".ember"
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
    @{
        provider = "ollama"
        base_url = "http://localhost:11434"
        preferred_model = $chosen
        adult_model = $chosen
        fallback_adult_model = $AdultBaseline
        high_heat_model = $AdultHighHeat
    } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $ConfigDir "local-models.json")

    Write-Host ""
    Write-Host "Local writing model installed and verified: $chosen" -ForegroundColor Green
    Write-Host "EmberWriter will prefer this model when Ollama is selected."
}

if (-not $SkipImageEngineInstall) {
    Write-Host ""
    Write-Host "Installing EmberWriter's managed image engine ($ImageEngine)..." -ForegroundColor Cyan
    $ImageInstaller = Join-Path $Root "scripts\install-image-engine.ps1"
    try {
        & $ImageInstaller -Engine $ImageEngine -SkipModelDownload:$SkipImageModelDownload
    } catch {
        Write-Host "Managed image-engine setup could not complete: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "EmberWriter itself is installed and will still run. Rerun install.ps1 later to repair image generation." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "Skipping managed Stable Diffusion image-engine installation." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete. Run .\start.ps1 to launch EmberWriter." -ForegroundColor Cyan