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
# Chunk 4: a separate CPU-only Ollama endpoint keeps story extraction from
# competing with the independent GPU-intensive scene-generation bakeoff.
$cpuHost = "http://127.0.0.1:11435"
$env:EMBER_STORY_OLLAMA_URL = $cpuHost
$cpuListen = Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (!$cpuListen) {
  $ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
  if (!(Test-Path $ollamaExe)) { throw "Local CPU Ollama binary not installed: $ollamaExe" }
  $env:OLLAMA_HOST = "127.0.0.1:11435"
  $env:OLLAMA_VULKAN = "false"
  $env:CUDA_VISIBLE_DEVICES = "-1"
  $env:ROCR_VISIBLE_DEVICES = "-1"
  $env:HIP_VISIBLE_DEVICES = "-1"
  $env:GGML_VK_VISIBLE_DEVICES = "-1"
  Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden -WorkingDirectory $root -RedirectStandardOutput (Join-Path $logs "ollama-cpu.stdout.log") -RedirectStandardError (Join-Path $logs "ollama-cpu.stderr.log") | Out-Null
  for ($i=0; $i -lt 25; $i++) {
    Start-Sleep -Milliseconds 600
    $cpuListen = Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cpuListen) { break }
  }
  if (!$cpuListen) { throw "CPU-only local Ollama did not bind port 11435" }
  Remove-Item Env:OLLAMA_HOST,Env:OLLAMA_VULKAN,Env:CUDA_VISIBLE_DEVICES,Env:ROCR_VISIBLE_DEVICES,Env:HIP_VISIBLE_DEVICES,Env:GGML_VK_VISIBLE_DEVICES -ErrorAction SilentlyContinue
}
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
