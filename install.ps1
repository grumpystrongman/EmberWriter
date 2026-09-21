param(
    [ValidateSet("auto", "4b", "8b", "12b", "14b", "24b")]
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

$AdultExplicit = "hf.co/mradermacher/Qwen3.5-4B-NSFW-ARA-Heretic-Literotica-i1-GGUF:Q4_K_M"
$GeneralProse = "hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M"
$CharacterModel = "hf.co/mradermacher/Pygmalion-3-12B-GGUF:Q4_K_M"
$AdultFast = "R4C3R/qwen3-8b-heretic:q4_k_m"
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

function Test-OllamaModelInstalled([string]$Model) {
    try {
        & ollama show $Model *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Stop-FrontendBuildProcesses {
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

        if ($stoppedAny) { Start-Sleep -Milliseconds 1000 }
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

# Persist GPU-friendly Ollama defaults. An already-running Ollama process keeps its old environment;
# EmberWriter's Performance panel includes a tuned restart button that applies these immediately.
$env:OLLAMA_FLASH_ATTENTION = "1"
$env:OLLAMA_KV_CACHE_TYPE = "q8_0"
$env:OLLAMA_NUM_PARALLEL = "1"
[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "q8_0", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "1", "User")
Write-Host "Ollama tuning: Flash Attention=on, KV cache=q8_0, parallel generations=1" -ForegroundColor Green

if (-not $SkipModelDownload) {
    $totalRamGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    $freeDiskGb = Get-FreeDiskGb $Root
    $chosen = $GeneralProse
    $modelsToInstall = @($AdultExplicit, $GeneralProse)

    if ($AdultModelTier -eq "4b") {
        $chosen = $AdultExplicit
        $modelsToInstall = @($AdultExplicit)
    } elseif ($AdultModelTier -eq "8b") {
        $chosen = $AdultFast
        $modelsToInstall = @($AdultFast, $AdultExplicit)
    } elseif ($AdultModelTier -eq "24b") {
        if ($freeDiskGb -lt $HighHeatMinimumFreeGb) {
            throw "The 24B high-heat model needs at least ${HighHeatMinimumFreeGb} GB free. Only ${freeDiskGb} GB is available."
        }
        $chosen = $AdultHighHeat
        $modelsToInstall = @($AdultExplicit, $AdultHighHeat)
    } elseif ($AdultModelTier -eq "auto") {
        # Auto provisions one specialist per major writing capability. Explicit adult scenes are
        # isolated to the proven 4B model; ordinary prose and character work stay on broader models.
        $modelsToInstall = @($AdultExplicit, $GeneralProse, $CharacterModel, $AdultFast)
    }

    Write-Host ""
    Write-Host "Adult explicit:    $AdultExplicit" -ForegroundColor Green
    Write-Host "General prose:     $GeneralProse" -ForegroundColor Green
    Write-Host "Character/dialogue:$CharacterModel" -ForegroundColor Green
    Write-Host "Planning / fast:   $AdultFast" -ForegroundColor Green
    Write-Host "Default model: $chosen"
    Write-Host "System RAM detected: ${totalRamGb} GB"
    Write-Host "Free disk detected: ${freeDiskGb} GB"
    if ($AdultModelTier -eq "auto") {
        Write-Host "Auto setup installs dedicated models for adult-explicit scenes, general prose, character/dialogue work, and fast planning."
    }

    foreach ($model in $modelsToInstall) {
        Write-Host "Downloading model if needed: $model"
        & ollama pull $model
        if ($LASTEXITCODE -ne 0) {
            throw "Ollama failed to download the managed writing model: $model"
        }
        if (-not (Test-OllamaModelInstalled $model)) {
            throw "Ollama reported a successful pull, but the managed writing model could not be opened: $model"
        }
    }

    $ConfigDir = Join-Path $Root ".ember"
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
    $preferred = if ($modelsToInstall -contains $GeneralProse) { $GeneralProse } else { $chosen }
    @{
        provider = "ollama"
        base_url = "http://localhost:11434"
        preferred_model = $preferred
        adult_model = $AdultExplicit
        adult_explicit_model = $AdultExplicit
        adult_candidate_model = $AdultExplicit
        general_prose_model = $GeneralProse
        quality_model = $GeneralProse
        creative_candidate_model = $GeneralProse
        character_model = $CharacterModel
        planning_model = $AdultFast
        fast_model = $AdultFast
        fallback_adult_model = $AdultExplicit
        high_heat_model = $AdultHighHeat
        adult_specialist_proof_sha256 = "95c9b55b72965adc59da1b026e8d771c5c9a9538385478d98fc0760edd234d51"
        adult_specialist_commercial_license_review_required = $true
        ollama_flash_attention = $true
        ollama_kv_cache_type = "q8_0"
        ollama_num_parallel = 1
    } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $ConfigDir "local-models.json")

    Write-Host ""
    Write-Host "Local writing models installed and verified." -ForegroundColor Green
    Write-Host "Validating the proven adult-explicit specialist on this local runtime..." -ForegroundColor Cyan
    & $Python -m app.model_bakeoff --attempts 3 --model $AdultExplicit
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Adult-explicit specialist passed local validation and was persisted for intent routing." -ForegroundColor Green
    } else {
        Write-Host "The adult-explicit specialist did not clear local validation. EmberWriter will keep the model installed and record the failure instead of silently substituting a different adult model." -ForegroundColor Yellow
    }
    Write-Host "Studio Auto routes explicit adult scenes to the proven specialist, general fiction to Magnum, character/dialogue work to Pygmalion, and planning/fast work to Qwen."
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
