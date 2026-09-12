param(
    [ValidateSet("auto", "8b", "14b")]
    [string]$AdultModelTier = "auto",
    [switch]$SkipModelDownload
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"

$Adult8B = "R4C3R/qwen3-8b-heretic:q4_k_m"
$Adult14B = "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m"

function Require-Command([string]$Name, [string]$Message) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw $Message
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

Write-Host "Installing frontend dependencies..."
Push-Location $Frontend
try { npm install } finally { Pop-Location }

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
    $chosen = $Adult8B
    if ($AdultModelTier -eq "14b" -or ($AdultModelTier -eq "auto" -and $totalRamGb -ge 24)) {
        $chosen = $Adult14B
    }
    if ($AdultModelTier -eq "8b") { $chosen = $Adult8B }

    Write-Host ""
    Write-Host "Recommended adult-fiction model: $chosen" -ForegroundColor Green
    Write-Host "System RAM detected: ${totalRamGb} GB"
    Write-Host "Downloading model if needed. This can take several minutes..."
    & ollama pull $chosen

    $ConfigDir = Join-Path $Root ".ember"
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
    @{
        provider = "ollama"
        base_url = "http://localhost:11434"
        preferred_model = $chosen
        adult_model = $chosen
        fallback_adult_model = $Adult8B
    } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $ConfigDir "local-models.json")

    Write-Host ""
    Write-Host "Local writing model installed: $chosen" -ForegroundColor Green
    Write-Host "EmberWriter will prefer this model when Ollama is selected."
}

Write-Host ""
Write-Host "Setup complete. Run .\start.ps1 to launch EmberWriter." -ForegroundColor Cyan
