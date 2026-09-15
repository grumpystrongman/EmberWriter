param(
    [ValidateSet("forge", "automatic1111")]
    [string]$Engine = "forge",
    [switch]$SkipModelDownload,
    [switch]$ForceReinstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ConfigDir = Join-Path $RepoRoot ".ember"
$RuntimeRoot = Join-Path $ConfigDir "image-engine"
$EngineDir = Join-Path $RuntimeRoot $Engine
$ConfigPath = Join-Path $ConfigDir "image-engine.json"
$Port = 7860
$BaseUrl = "http://127.0.0.1:$Port"

$EngineRepos = @{
    forge = @{
        repo = "https://github.com/lllyasviel/stable-diffusion-webui-forge.git"
        branch = "main"
        display = "Stable Diffusion WebUI Forge"
    }
    automatic1111 = @{
        repo = "https://github.com/AUTOMATIC1111/stable-diffusion-webui.git"
        branch = "master"
        display = "AUTOMATIC1111 Stable Diffusion WebUI"
    }
}

$DefaultModel = @{
    file = "emberwriter-sd15-v1-5-pruned-emaonly.safetensors"
    url = "https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors?download=true"
    sha256 = "6ce0161689b3853acaa03779ec93eafe75a02f4ced659bee03f50797806fa2fa"
    source = "stable-diffusion-v1-5/stable-diffusion-v1-5"
    license = "CreativeML Open RAIL-M"
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Find-Python310 {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $result = & $launcher.Source -3.10 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $result) {
                $candidate = ($result | Select-Object -Last 1).Trim()
                if (Test-Path $candidate) { return $candidate }
            }
        } catch { }
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"),
        (Join-Path $env:ProgramFiles "Python310\python.exe")
    )
    if (${env:ProgramFiles(x86)}) {
        $candidates += Join-Path ${env:ProgramFiles(x86)} "Python310\python.exe"
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return $null
}

function Ensure-Python310 {
    $python = Find-Python310
    if ($python) { return $python }

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Python 3.10 is required by Stable Diffusion WebUI on Windows. Install Python 3.10 or install winget, then rerun setup."
    }

    Write-Host "Installing Python 3.10 for the managed image engine..." -ForegroundColor Yellow
    & $winget.Source install --exact --id Python.Python.3.10 --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "winget could not install Python 3.10 (exit code $LASTEXITCODE)."
    }
    Refresh-ProcessPath
    $python = Find-Python310
    if (-not $python) {
        throw "Python 3.10 installation completed, but EmberWriter could not locate python.exe. Open a new PowerShell window and rerun install.ps1."
    }
    return $python
}

function Ensure-Git {
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($git) { return $git.Source }

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Git is required to install the managed image engine. Install Git or winget, then rerun setup."
    }

    Write-Host "Installing Git for the managed image engine..." -ForegroundColor Yellow
    & $winget.Source install --exact --id Git.Git --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "winget could not install Git (exit code $LASTEXITCODE)."
    }
    Refresh-ProcessPath
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $git) {
        throw "Git installation completed, but git.exe is not available in this terminal. Open a new PowerShell window and rerun install.ps1."
    }
    return $git.Source
}

function Download-LargeFile([string]$Url, [string]$Destination) {
    $partial = "$Destination.partial"
    if (Test-Path $partial) { Remove-Item -Force $partial }

    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & $curl.Source -L --fail --retry 4 --retry-delay 2 --output $partial $Url
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -Force $partial -ErrorAction SilentlyContinue
            throw "Model download failed with curl exit code $LASTEXITCODE."
        }
    } elseif (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
        Start-BitsTransfer -Source $Url -Destination $partial -DisplayName "EmberWriter Stable Diffusion model"
    } else {
        Invoke-WebRequest -Uri $Url -OutFile $partial -UseBasicParsing
    }

    Move-Item -Force $partial $Destination
}

function Ensure-DefaultModel([string]$InstallPath) {
    $modelDir = Join-Path $InstallPath "models\Stable-diffusion"
    New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
    $modelPath = Join-Path $modelDir $DefaultModel.file

    if (Test-Path $modelPath) {
        $hash = (Get-FileHash -Algorithm SHA256 $modelPath).Hash.ToLowerInvariant()
        if ($hash -eq $DefaultModel.sha256) {
            Write-Host "Image model already verified: $($DefaultModel.file)" -ForegroundColor Green
            return $modelPath
        }
        Write-Host "Existing image model failed SHA-256 verification; replacing it." -ForegroundColor Yellow
        Remove-Item -Force $modelPath
    }

    Write-Host "Downloading the baseline Stable Diffusion 1.5 checkpoint (4.27 GB)..." -ForegroundColor Cyan
    Download-LargeFile $DefaultModel.url $modelPath
    $downloadedHash = (Get-FileHash -Algorithm SHA256 $modelPath).Hash.ToLowerInvariant()
    if ($downloadedHash -ne $DefaultModel.sha256) {
        Remove-Item -Force $modelPath -ErrorAction SilentlyContinue
        throw "Downloaded Stable Diffusion checkpoint failed SHA-256 verification. Expected $($DefaultModel.sha256), got $downloadedHash."
    }
    Write-Host "Stable Diffusion checkpoint verified." -ForegroundColor Green
    return $modelPath
}

function Test-PythonPip([string]$PythonPath) {
    if (-not $PythonPath -or -not (Test-Path $PythonPath)) { return $false }
    try {
        & $PythonPath -m pip --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Repair-PythonPip([string]$PythonPath) {
    Write-Host "Repairing pip inside the Stable Diffusion Python environment..." -ForegroundColor Yellow
    try {
        & $PythonPath -m ensurepip --upgrade
        if ($LASTEXITCODE -eq 0 -and (Test-PythonPip $PythonPath)) {
            Write-Host "pip repaired successfully." -ForegroundColor Green
            return $true
        }
    } catch { }
    return $false
}

function New-ForgeVenv([string]$BasePython, [string]$InstallPath) {
    $venvDir = Join-Path $InstallPath "venv"
    $runtimePython = Join-Path $venvDir "Scripts\python.exe"

    if (Test-Path $runtimePython) {
        if (Test-PythonPip $runtimePython) { return $runtimePython }

        Write-Host "Stable Diffusion Python environment exists but pip is missing or broken." -ForegroundColor Yellow
        if (Repair-PythonPip $runtimePython) { return $runtimePython }

        Write-Host "pip could not be repaired in place; rebuilding the Stable Diffusion Python environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir
    } elseif (Test-Path $venvDir) {
        Remove-Item -Recurse -Force $venvDir
    }

    Write-Host "Creating Stable Diffusion Python environment..." -ForegroundColor Cyan
    & $BasePython -m venv $venvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $runtimePython)) {
        throw "Could not create the Stable Diffusion Python environment with $BasePython."
    }

    if (-not (Test-PythonPip $runtimePython)) {
        if (-not (Repair-PythonPip $runtimePython)) {
            throw "The Stable Diffusion Python environment was created, but pip is unavailable and ensurepip could not repair it. Repair/reinstall Python 3.10 and rerun install.ps1."
        }
    }

    return $runtimePython
}

function Prepare-ForgeRuntime([string]$BasePython, [string]$InstallPath) {
    $venvDir = Join-Path $InstallPath "venv"

    for ($attempt = 1; $attempt -le 2; $attempt++) {
        $runtimePython = New-ForgeVenv -BasePython $BasePython -InstallPath $InstallPath
        Write-Host "Preparing Stable Diffusion runtime dependencies..." -ForegroundColor Cyan
        Write-Host "This is installation/repair work; normal EmberWriter startup will not reinstall these packages." -ForegroundColor DarkGray

        Push-Location $InstallPath
        try {
            & $runtimePython "launch.py" "--exit" "--no-download-sd-model"
            $exitCode = $LASTEXITCODE
        } finally {
            Pop-Location
        }

        if ($exitCode -eq 0) {
            Write-Host "Stable Diffusion runtime dependencies are ready." -ForegroundColor Green
            return $runtimePython
        }

        if ($attempt -eq 1) {
            Write-Host "Forge dependency setup failed. Rebuilding its Python environment once..." -ForegroundColor Yellow
            if (Test-Path $venvDir) { Remove-Item -Recurse -Force $venvDir }
            continue
        }

        throw "Forge runtime preparation failed with exit code $exitCode."
    }

    throw "Forge runtime preparation did not complete."
}

New-Item -ItemType Directory -Force -Path $ConfigDir, $RuntimeRoot | Out-Null
$selected = $EngineRepos[$Engine]
$python310 = Ensure-Python310
$git = Ensure-Git

if ($ForceReinstall -and (Test-Path $EngineDir)) {
    Write-Host "Removing existing managed $Engine installation..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $EngineDir
}

if (Test-Path (Join-Path $EngineDir ".git")) {
    Write-Host "Updating managed $($selected.display)..." -ForegroundColor Cyan
    & $git -C $EngineDir remote set-url origin $selected.repo
    & $git -C $EngineDir fetch --prune origin $selected.branch
    if ($LASTEXITCODE -ne 0) { throw "Could not fetch image-engine updates." }
    & $git -C $EngineDir checkout $selected.branch
    if ($LASTEXITCODE -ne 0) { throw "Could not select image-engine branch $($selected.branch)." }
    & $git -C $EngineDir pull --ff-only origin $selected.branch
    if ($LASTEXITCODE -ne 0) { throw "Could not update the managed image engine cleanly." }
} else {
    if (Test-Path $EngineDir) { Remove-Item -Recurse -Force $EngineDir }
    Write-Host "Installing managed $($selected.display)..." -ForegroundColor Cyan
    & $git clone --depth 1 --branch $selected.branch $selected.repo $EngineDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $EngineDir "launch.py"))) {
        throw "The image-engine repository did not install correctly."
    }
}

$modelPath = $null
$modelSource = $null
$modelLicense = $null
$modelSha256 = $null
if (-not $SkipModelDownload) {
    $modelPath = Ensure-DefaultModel $EngineDir
    $modelSource = $DefaultModel.source
    $modelLicense = $DefaultModel.license
    $modelSha256 = $DefaultModel.sha256
} else {
    Write-Host "Skipping baseline image-model download. Add a checkpoint under models\Stable-diffusion before generating images." -ForegroundColor Yellow
}

$runtimePython = Prepare-ForgeRuntime -BasePython $python310 -InstallPath $EngineDir
$launchArgs = @("--nowebui", "--api", "--port", "$Port", "--no-download-sd-model")

$config = @{
    schema_version = 2
    managed = $true
    engine = $Engine
    display_name = $selected.display
    repository = $selected.repo
    branch = $selected.branch
    install_path = $EngineDir
    python = $python310
    runtime_python = $runtimePython
    base_url = $BaseUrl
    port = $Port
    launcher = (Join-Path $EngineDir "launch.py")
    launch_args = $launchArgs
    bootstrap_complete = $true
    model = $modelPath
    model_source = $modelSource
    model_license = $modelLicense
    model_sha256 = $modelSha256
    installed_at = (Get-Date).ToUniversalTime().ToString("o")
}
$config | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $ConfigPath

Write-Host ""
Write-Host "Managed image engine installed: $($selected.display)" -ForegroundColor Green
Write-Host "Location: $EngineDir"
Write-Host "API:      $BaseUrl"
if ($modelPath) { Write-Host "Model:    $modelPath" }
Write-Host "EmberWriter will start the API-only image service automatically from start.ps1."
