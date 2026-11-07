$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DataDir = Join-Path $env:LOCALAPPDATA "EmberWriter\PinokioAuthorData"
if (-not $env:LOCALAPPDATA) { throw "Windows local application data folder was not found." }
$Exe = Join-Path $Root "backend\.venv\Scripts\python.exe"
$Vite = Join-Path $Root "frontend\node_modules\.bin\vite.cmd"
if (-not (Test-Path $Exe) -or -not (Test-Path $Vite)) {
    throw "Writer-only installation missing. Run Install in Pinokio first."
}
foreach ($Port in @(8000, 5173)) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port $Port is already in use. Close the other app before launching; this preview will not kill it."
    }
}
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
Write-Host "Opening EmberWriter with persistent author data: $DataDir"
& (Join-Path $Root "start.ps1") -SkipManagedImageEngine -DataDir $DataDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
