param(
    [switch]$PassThru,
    [switch]$WaitForReady,
    [ValidateRange(10, 1800)]
    [int]$ReadyTimeoutSeconds = 1200,
    [ValidateRange(1, 60)]
    [int]$ProbeTimeoutSeconds = 10
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
    $deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-ImageApi $baseUrl) {
            $ready = $true
            break
        }
        if ($process.HasExited) { break }
        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        $tail = ""
        if (Test-Path $stderr) {
            $tail = (Get-Content $stderr -Tail 40 -ErrorAction SilentlyContinue) -join "`n"
        }
        if (-not $tail -and (Test-Path $stdout)) {
            $tail = (Get-Content $stdout -Tail 40 -ErrorAction SilentlyContinue) -join "`n"
        }
        $detail = ""
        if ($tail) { $detail = "`n`nLast log lines:`n$tail" }
        throw "The managed image engine did not become ready at $baseUrl. Check $stdout and $stderr.$detail"
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
