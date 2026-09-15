param(
    [switch]$PassThru,
    [switch]$WaitForReady,
    [ValidateRange(10, 1800)]
    [int]$ReadyTimeoutSeconds = 1200,
    [ValidateRange(1, 60)]
    [int]$ProbeTimeoutSeconds = 10,
    [ValidateRange(5, 120)]
    [int]$ProgressIntervalSeconds = 10
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $RepoRoot ".ember\image-engine.json"
$LogDir = Join-Path $RepoRoot ".ember\logs"

function Test-ImageApi([string]$BaseUrl) {
    $response = $null
    try {
        # Bypass Windows/system proxies explicitly. A corporate proxy intercepting
        # localhost makes a healthy Forge/A1111 API look like a repeated timeout.
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

function Clear-StaleManagedListener([int]$Port, [string]$InstallPath) {
    $listenerProcessId = Get-ListenerProcessId $Port
    if (-not $listenerProcessId) { return }

    if (-not (Test-IsManagedImageProcess $listenerProcessId $InstallPath)) {
        throw "Port $Port is already owned by another process (PID $listenerProcessId). Stop that service or change the managed image-engine port before starting EmberWriter."
    }

    Write-Host "Stopping stale managed image-engine process on port $Port (PID $listenerProcessId)..." -ForegroundColor Yellow
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
            $candidates += [pscustomobject]@{
                Path = $path
                Line = [string]$lines[-1]
                Modified = (Get-Item $path -ErrorAction SilentlyContinue).LastWriteTimeUtc
            }
        }
    }
    if ($candidates.Count -eq 0) { return $null }
    return $candidates | Sort-Object Modified -Descending | Select-Object -First 1
}

if (-not (Test-Path $ConfigPath)) {
    throw "Managed image engine is not installed. Run .\install.ps1 to install Forge automatically."
}

$config = Get-Content -Raw $ConfigPath | ConvertFrom-Json
if (-not $config.managed) {
    throw "The configured image engine is not marked as EmberWriter-managed."
}

$installPath = [string]$config.install_path
$launcher = [string]$config.launcher
$baseUrl = [string]$config.base_url
$python = [string]$config.python
$launchArgs = @($config.launch_args | ForEach-Object { [string]$_ })
$port = 7860
if ($config.port) {
    $port = [int]$config.port
} else {
    try { $port = ([uri]$baseUrl).Port } catch { }
}

# Older/stale image-engine.json files may predate the API arguments. Enforce the
# contract here as well as in the installer so an existing install repairs itself.
if (-not ($launchArgs -contains "--api")) {
    $launchArgs = @("--api") + $launchArgs
}
if (-not ($launchArgs -contains "--port")) {
    $launchArgs += @("--port", "$port")
}

if (-not (Test-Path $installPath)) {
    throw "Managed image-engine folder is missing: $installPath. Rerun .\install.ps1."
}
if (-not (Test-Path $launcher)) {
    throw "Managed image-engine launcher is missing: $launcher. Rerun .\install.ps1."
}
if ($python -and -not (Test-Path $python)) {
    throw "Python 3.10 used by the image engine is missing: $python. Rerun .\install.ps1."
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

# If a previous managed Forge launch is wedged while still holding the API port,
# replace it before starting another copy. Never kill an unrelated listener.
Clear-StaleManagedListener -Port $port -InstallPath $installPath

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stdout = Join-Path $LogDir "image-engine.out.log"
$stderr = Join-Path $LogDir "image-engine.err.log"
Remove-Item -Force $stdout, $stderr -ErrorAction SilentlyContinue

$previousPython = $env:PYTHON
try {
    if ($python) { $env:PYTHON = $python }
    $quotedLauncher = '"' + $launcher + '"'
    $command = $quotedLauncher
    if ($launchArgs.Count -gt 0) { $command += " " + ($launchArgs -join " ") }

    Write-Host "Starting $($config.display_name) at $baseUrl..." -ForegroundColor Cyan
    Write-Host "Forge first-run setup can take several minutes. Startup progress will appear below." -ForegroundColor DarkGray
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList @("/d", "/s", "/c", $command) `
        -WorkingDirectory $installPath -WindowStyle Minimized -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
} finally {
    $env:PYTHON = $previousPython
}

$ready = $false
# start.ps1 uses -PassThru because it needs the process id for cleanup. Treat that
# as a managed startup request and do not open EmberWriter until the API is usable.
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
                Write-Host "Forge [$($elapsed)s]: still starting; waiting for /sdapi/v1/options..." -ForegroundColor DarkGray
            }
            $nextProgressAt = $now.AddSeconds($ProgressIntervalSeconds)
        }
        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        $tail = ""
        if (Test-Path $stderr) {
            $tail = (Get-Content $stderr -Tail 60 -ErrorAction SilentlyContinue) -join "`n"
        }
        if (Test-Path $stdout) {
            $stdoutTail = (Get-Content $stdout -Tail 60 -ErrorAction SilentlyContinue) -join "`n"
            if ($stdoutTail) {
                if ($tail) { $tail += "`n`n" }
                $tail += $stdoutTail
            }
        }
        $detail = ""
        if ($tail) { $detail = "`n`nLast Forge log lines:`n$tail" }
        if ($process.HasExited) {
            throw "The managed image engine exited before its API became ready (exit code $($process.ExitCode)). Check $stdout and $stderr.$detail"
        }
        throw "The managed image engine did not become ready at $baseUrl within $ReadyTimeoutSeconds seconds. Check $stdout and $stderr.$detail"
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
