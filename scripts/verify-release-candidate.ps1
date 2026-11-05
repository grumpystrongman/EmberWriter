param([switch]$SkipFrontend = $false)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = Join-Path $Root "backend\.venv\Scripts\python.exe" }
if (-not (Test-Path $Python)) { throw "Python virtual environment not prepared" }
$original = $env:EMBER_DATA_DIR
$env:EMBER_DATA_DIR = Join-Path $Root ".ember\rc-synthetic-qa"
try {
    Push-Location (Join-Path $Root "backend")
    & $Python -c "from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app); c.__enter__(); h=c.get('/api/health'); print(h.json()); assert h.status_code==200 and h.json()['version']=='0.15.0rc1'; assert c.get('/openapi.json').status_code==200; c.__exit__(None,None,None)"
    if ($LASTEXITCODE -ne 0) { throw "Backend API smoke failed" }
    Pop-Location
    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Python dependency check failed" }
    if (-not $SkipFrontend) {
        $Dist = Join-Path $Root "frontend\dist"
        if (-not (Test-Path $Dist)) { throw "Frontend dist missing: build frontend first" }
        $files = Get-ChildItem -Path $Dist -Recurse -File
        $JS = $files | Where-Object Extension -EQ ".js"
        $Oversized = $JS | Where-Object Length -GT 512000
        if ($Oversized) { throw "Frontend JS chunk budget exceeded" }
        $bundles = ($files | Where-Object Extension -In @(".js",".html") | ForEach-Object { Get-Content $_.FullName -Raw }) -join ""
        if ($bundles.Contains("127.0.0.1:8000/api")) { throw "Local URL leaked into hosted build" }
        if (-not $bundles.Contains("https://api.example.invalid/api")) { throw "Hosted API rewrite missing" }
        Write-Host "Frontend hosted build and chunk budget passed" -ForegroundColor Green
    }
    Write-Host "EmberWriter 0.15.0rc1 basic candidate smoke passed" -ForegroundColor Green
}
finally {
    Pop-Location -ErrorAction SilentlyContinue
    $env:EMBER_DATA_DIR = $original
}
