param(
    [switch]$PassThru,
    [switch]$WaitForReady,
    [ValidateRange(10, 600)]
    [int]$ReadyTimeoutSeconds = 180,
    [ValidateRange(1, 30)]
    [int]$ProbeTimeoutSeconds = 5,
    [ValidateRange(5, 60)]
    [int]$ProgressIntervalSeconds = 10
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $RepoRoot ".ember\image-engine.json"
$LogDir = Join-Path $RepoRoot ".ember\logs"

function Test-ImageApi([string]$BaseUrl) {
    $response = $null
    try {
        # Local image traffic must never be routed through a system/corporate proxy.
        $request = [System.Net.HttpWebRequest]::Create("$($BaseUrl.TrimEnd('/'))/sdapi/v1/options")
        $request.Method = "GET"
        $request.Proxy = $null
        $request.Timeout = $ProbeTimeoutSeconds * 1000
        $request.ReadWriteTimeout = $ProbeTimeoutSeconds * 1000
        $response = $request.GetResponse()
        return ([int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 300)
    } catch {
        return $false
    } finally {
        if ($response) { $response.Close() }
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

function Test-IsManagedImageProcess([int]$ProcessId, [string]$InstallPath) {
    try {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        if (-not $processInfo) { return $false }
        $installFull = [System.IO.Path]::GetFullPath($InstallPath)
        foreach ($candidate in @([string]$processInfo.ExecutablePath, [string]$processInfo.CommandLine)) {
            if ($candidate -and $candidate.IndexOf($installFull, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                return $true
            }
        }
    } catch { }
    return $false
}

function Stop-StaleManagedImageProcesses([string]$InstallPath) {
    $installFull = [System.IO.Path]::GetFullPath($InstallPath)
    $candidateNames = @("python.exe", "pythonw.exe", "cmd.exe")
    try {
        $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.ProcessId -ne $PID -and
            $candidateNames -contains $_.Name.ToLowerInvariant() -and
            $_.CommandLine -and
            $_.CommandLine.IndexOf($installFull, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        }

        foreach ($item in $processes) {
            $processId = [int]$item.ProcessId
            Write-Host "Stopping stale managed image-engine process (PID $processId)..." -ForegroundColor Yellow
            try {
                & taskkill.exe /PID $processId /T /F 2>$null | Out-Null
            } catch {
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
        }
        if ($processes) { Start-Sleep -Milliseconds 750 }
    } catch {
        Write-Host "Could not inspect stale image-engine processes: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Clear-StaleManagedListener([int]$Port, [string]$InstallPath) {
    $listenerProcessId = Get-ListenerProcessId $Port
    if (-not $listenerProcessId) { return }

    if (-not (Test-IsManagedImageProcess $listenerProcessId $InstallPath)) {
        throw "Port $Port is already owned by another process (PID $listenerProcessId). Stop that service or change the managed image-engine port before starting EmberWriter."
    }

    Write-Host "Stopping stale managed image-engine listener on port $Port (PID $listenerProcessId)..." -ForegroundColor Yellow
    try {
        & taskkill.exe /PID $listenerProcessId /T /F 2>$null | Out-Null
    } catch {
        Stop-Process -Id $listenerProcessId -Force -ErrorAction SilentlyContinue
    }

    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (-not (Get-ListenerProcessId $Port)) { return }
    }
    throw "The stale managed image engine on port $Port did not stop cleanly. End its Python process and rerun start.ps1."
}

function Get-LogProgressLine([string]$StdoutPath, [string]$StderrPath) {
    $candidates = @()
    foreach ($path in @($StderrPath, $StdoutPath)) {
        if (-not (Test-Path $path)) { continue }
        $lines = @(Get-Content -Path $path -Tail 25 -ErrorAction SilentlyContinue | Where-Object { $_ -and $_.Trim() })
        if ($lines.Count -gt 0) {
            $item = Get-Item $path -ErrorAction SilentlyContinue
            $modified = [DateTime]::MinValue
            if ($item) { $modified = $item.LastWriteTimeUtc }
            $candidates += [pscustomobject]@{
                Path = $path
                Line = [string]$lines[-1]
                Modified = $modified
            }
        }
    }
    if ($candidates.Count -eq 0) { return $null }
    return $candidates | Sort-Object Modified -Descending | Select-Object -First 1
}

function Get-ForgeLogTail([string]$StdoutPath, [string]$StderrPath) {
    $parts = @()
    foreach ($path in @($StderrPath, $StdoutPath)) {
        if (-not (Test-Path $path)) { continue }
        $text = (Get-Content $path -Tail 100 -ErrorAction SilentlyContinue) -join "`n"
        if ($text) { $parts += $text }
    }
    return ($parts -join "`n`n")
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

function Ensure-ForgeVenv([string]$BasePython, [string]$InstallPath) {
    $venvDir = Join-Path $InstallPath "venv"
    $runtimePython = Join-Path $venvDir "Scripts\python.exe"

    if (Test-Path $runtimePython) {
        if (Test-PythonPip $runtimePython) { return $runtimePython }

        Write-Host "Forge Python environment exists but pip is missing or broken." -ForegroundColor Yellow
        if (Repair-PythonPip $runtimePython) { return $runtimePython }

        Write-Host "pip could not be repaired in place; rebuilding the Forge Python environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir
    } elseif (Test-Path $venvDir) {
        Write-Host "Removing incomplete Forge Python environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir
    }

    Write-Host "Creating Forge Python environment..." -ForegroundColor Cyan
    & $BasePython -m venv $venvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $runtimePython)) {
        throw "Could not create Forge's Python environment with $BasePython."
    }

    if (-not (Test-PythonPip $runtimePython)) {
        if (-not (Repair-PythonPip $runtimePython)) {
            throw "Forge's Python environment was created, but pip is unavailable and ensurepip could not repair it. Repair/reinstall Python 3.10 and rerun EmberWriter."
        }
    }

    return $runtimePython
}

function Save-ImageEngineConfig([object]$Config) {
    $Config | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $ConfigPath
}

function Set-ConfigProperty([object]$Config, [string]$Name, $Value) {
    if ($Config.PSObject.Properties[$Name]) {
        $Config.$Name = $Value
    } else {
        $Config | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Initialize-ForgeRuntime(
    [string]$RuntimePython,
    [string]$InstallPath,
    [object]$Config,
    [string[]]$LaunchArgs
) {
    $needsBootstrap = $true
    if ($Config.PSObject.Properties["bootstrap_complete"]) {
        $needsBootstrap = -not [bool]$Config.bootstrap_complete
    }

    if (-not $needsBootstrap) { return }

    Write-Host ""
    Write-Host "Preparing Stable Diffusion runtime (one-time repair)..." -ForegroundColor Cyan
    Write-Host "Forge will validate/install Torch and its Python dependencies now. Any failure will be shown here immediately." -ForegroundColor DarkGray

    Push-Location $InstallPath
    try {
        # Forge's --exit mode performs dependency/bootstrap work but does not start
        # Gradio or wait for an interactive batch-file pause.
        & $RuntimePython "launch.py" "--exit" "--no-download-sd-model"
        if ($LASTEXITCODE -ne 0) {
            throw "Forge runtime preparation failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }

    Set-ConfigProperty $Config "schema_version" 2
    Set-ConfigProperty $Config "runtime_python" $RuntimePython
    Set-ConfigProperty $Config "launcher" (Join-Path $InstallPath "launch.py")
    Set-ConfigProperty $Config "launch_args" $LaunchArgs
    Set-ConfigProperty $Config "bootstrap_complete" $true
    Save-ImageEngineConfig $Config
    Write-Host "Stable Diffusion runtime prepared successfully." -ForegroundColor Green
}

if (-not (Test-Path $ConfigPath)) {
    throw "Managed image engine is not installed. Run .\install.ps1 to install Forge automatically."
}

$config = Get-Content -Raw $ConfigPath | ConvertFrom-Json
if (-not $config.managed) {
    throw "The configured image engine is not marked as EmberWriter-managed."
}

$installPath = [string]$config.install_path
$baseUrl = [string]$config.base_url
$basePython = [string]$config.python
$launchArgs = @($config.launch_args | ForEach-Object { [string]$_ })
$port = 7860
if ($config.port) {
    $port = [int]$config.port
} else {
    try { $port = ([uri]$baseUrl).Port } catch { }
}

if (-not (Test-Path $installPath)) {
    throw "Managed image-engine folder is missing: $installPath. Rerun .\install.ps1."
}
$launchPy = Join-Path $installPath "launch.py"
if (-not (Test-Path $launchPy)) {
    throw "Managed image-engine launch.py is missing: $launchPy. Rerun .\install.ps1."
}
if (-not $basePython -or -not (Test-Path $basePython)) {
    throw "Python 3.10 used by the image engine is missing: $basePython. Rerun .\install.ps1."
}

# Normalize old schema-1 configurations in memory. The repaired config is saved
# after a successful bootstrap.
if (-not ($launchArgs -contains "--api")) {
    $launchArgs = @("--api") + $launchArgs
}
if (-not ($launchArgs -contains "--nowebui")) {
    $launchArgs = @("--nowebui") + $launchArgs
}
if (-not ($launchArgs -contains "--port")) {
    $launchArgs += @("--port", "$port")
}
if (-not ($launchArgs -contains "--no-download-sd-model")) {
    $launchArgs += "--no-download-sd-model"
}

if (Test-ImageApi $baseUrl) {
    Write-Host "Image engine already ready: $baseUrl" -ForegroundColor Green
    if ($PassThru) {
        [pscustomobject]@{
            Started = $false
            Pid = $null
            BaseUrl = $baseUrl
            Engine = [string]$config.engine
            Ready = $true
        }
    }
    return
}

# Clean up both the old hidden batch/cmd wrapper and any stale direct Python
# Forge launch before repairing or starting the engine.
Stop-StaleManagedImageProcesses -InstallPath $installPath
Clear-StaleManagedListener -Port $port -InstallPath $installPath

$runtimePython = Ensure-ForgeVenv -BasePython $basePython -InstallPath $installPath
Initialize-ForgeRuntime -RuntimePython $runtimePython -InstallPath $installPath -Config $config -LaunchArgs $launchArgs

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stdout = Join-Path $LogDir "image-engine.out.log"
$stderr = Join-Path $LogDir "image-engine.err.log"
Remove-Item -Force $stdout, $stderr -ErrorAction SilentlyContinue

Write-Host "Starting $($config.display_name) API at $baseUrl..." -ForegroundColor Cyan
$argumentList = @("launch.py") + $launchArgs
$process = Start-Process -FilePath $runtimePython -ArgumentList $argumentList `
    -WorkingDirectory $installPath -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr

$ready = $false
if ($WaitForReady -or $PassThru) {
    $startedAt = Get-Date
    $deadline = $startedAt.AddSeconds($ReadyTimeoutSeconds)
    $nextProgressAt = $startedAt
    $lastProgressLine = ""

    while ((Get-Date) -lt $deadline) {
        if (Test-ImageApi $baseUrl) {
            $ready = $true
            break
        }
        if ($process.HasExited) { break }

        $now = Get-Date
        if ($now -ge $nextProgressAt) {
            $progress = Get-LogProgressLine -StdoutPath $stdout -StderrPath $stderr
            $elapsed = [int](($now - $startedAt).TotalSeconds)
            if ($progress -and $progress.Line -ne $lastProgressLine) {
                Write-Host "Forge [$($elapsed)s]: $($progress.Line)" -ForegroundColor DarkGray
                $lastProgressLine = $progress.Line
            } elseif ($elapsed -gt 0) {
                Write-Host "Forge [$($elapsed)s]: starting API..." -ForegroundColor DarkGray
            }
            $nextProgressAt = $now.AddSeconds($ProgressIntervalSeconds)
        }
        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        $tail = Get-ForgeLogTail -StdoutPath $stdout -StderrPath $stderr
        $detail = ""
        if ($tail) { $detail = "`n`nLast Forge log lines:`n$tail" }

        if ($process.HasExited) {
            throw "Stable Diffusion Forge exited before its API became ready (exit code $($process.ExitCode)).$detail"
        }

        try { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue } catch { }
        throw "Stable Diffusion Forge did not become ready at $baseUrl within $ReadyTimeoutSeconds seconds. The process was stopped.$detail"
    }

    Write-Host "Image engine ready: $baseUrl" -ForegroundColor Green
}

if ($PassThru) {
    [pscustomobject]@{
        Started = $true
        Pid = $process.Id
        BaseUrl = $baseUrl
        Engine = [string]$config.engine
        Ready = $ready
        Stdout = $stdout
        Stderr = $stderr
    }
}
