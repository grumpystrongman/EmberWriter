param(
    [int]$Runs = 10,
    [double]$RequiredPassRate = 0.90,
    [string]$PromptFile = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
$Harness = Join-Path $Root "scripts\writing_acceptance.py"

if (-not (Test-Path $Python)) {
    throw "EmberWriter's backend environment is missing at $Python. Run .\install.ps1 first."
}
if (-not (Test-Path $Harness)) {
    throw "Writing acceptance harness is missing at $Harness."
}

$argsList = @(
    $Harness,
    "--runs", $Runs,
    "--required-pass-rate", $RequiredPassRate
)

if ($PromptFile) {
    $resolvedPrompt = [System.IO.Path]::GetFullPath($PromptFile)
    if (-not (Test-Path $resolvedPrompt)) {
        throw "Prompt file was not found: $resolvedPrompt"
    }
    $argsList += @("--prompt-file", $resolvedPrompt)
}

Write-Host "Running EmberWriter real-model writing acceptance..." -ForegroundColor Cyan
Write-Host "Runs:             $Runs"
Write-Host "Required pass:    $([Math]::Round($RequiredPassRate * 100))%"
Write-Host "Generated prose is not printed or stored; only pass/fail metrics are retained." -ForegroundColor DarkGray

& $Python @argsList
if ($LASTEXITCODE -ne 0) {
    throw "Writing acceptance failed. See .ember\acceptance\writing-acceptance-latest.json for metrics."
}

Write-Host "Writing acceptance passed." -ForegroundColor Green
