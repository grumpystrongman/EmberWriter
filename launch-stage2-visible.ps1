# Local Stage 2 launcher. Keeps the existing library and the original checkout untouched.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$data = "C:\Users\grump\projects\EmberWriter-Part1-Verify\part1-demo-data-v2"
$python = "C:\Users\grump\projects\EmberWriter-Part1-Verify\.venv\Scripts\python.exe"
$vite = Join-Path $root "frontend\node_modules\vite\bin\vite.js"
$logs = Join-Path $root ".ember"
New-Item -ItemType Directory -Path $logs -Force | Out-Null
foreach ($path in @($data, $python, $vite)) {
  if (!(Test-Path $path)) { throw "Missing prerequisite: $path" }
}
$env:EMBER_DATA_DIR = $data
# Refuse to stop unrelated programs. Only replace EmberWriter listeners.
foreach ($port in @(5173, 8000)) {
  $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($listener) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    $cmd = [string]$process.CommandLine
    if ($port -eq 5173 -and $cmd -notmatch 'vite') { throw "Port 5173 belongs to another app: $cmd" }
    if ($port -eq 8000 -and $cmd -notmatch 'uvicorn') { throw "Port 8000 belongs to another app: $cmd" }
    Stop-Process -Id $listener.OwningProcess -Force
  }
}
Start-Sleep -Seconds 2
$backend = Start-Process -FilePath $python -ArgumentList @("-m","uvicorn","app.main:app","--app-dir",(Join-Path $root "backend"),"--host","127.0.0.1","--port","8000") -WorkingDirectory $root -RedirectStandardOutput (Join-Path $logs "stage2-backend.out.log") -RedirectStandardError (Join-Path $logs "stage2-backend.err.log") -PassThru
$frontend = Start-Process -FilePath "node.exe" -ArgumentList @($vite,"--host","127.0.0.1","--port","5173","--strictPort") -WorkingDirectory (Join-Path $root "frontend") -RedirectStandardOutput (Join-Path $logs "stage2-frontend.out.log") -RedirectStandardError (Join-Path $logs "stage2-frontend.err.log") -PassThru
$ready = $false
for ($i=0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try {
    $health = Invoke-RestMethod "http://127.0.0.1:8000/api/health" -TimeoutSec 2
    $ui = Invoke-WebRequest "http://127.0.0.1:5173/" -TimeoutSec 2 -UseBasicParsing
    if ($health.ok -eq $true -and $ui.StatusCode -eq 200) { $ready = $true; break }
  } catch {}
}
if (!$ready) { throw "Stage 2 services did not become healthy. Check $logs" }
Write-Host "Stage 2 EmberWriter: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "Data preserved at: $data" -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5173"
