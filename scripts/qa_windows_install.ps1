# Run only on a synthetic isolated archive, never on the author's checkout.
# This same-host test is NOT a fresh Windows OS or Pinokio GUI certification.
param([string]$EvidenceRoot = "")
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $env:TEMP ("EmberWriter Release QA " + [guid]::NewGuid().ToString("N")) }
if (Test-Path $EvidenceRoot) { throw "Choose a new isolated QA folder; refusing to overwrite data." }
New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null
$Archive = Join-Path $EvidenceRoot "source.zip"
$Application = Join-Path $EvidenceRoot "Application With Spaces"
$DataDir = Join-Path $EvidenceRoot "Author QA With Spaces"
New-Item -ItemType Directory -Path $Application, $DataDir -Force | Out-Null
Push-Location $Repo
try {
    & git archive --format=zip HEAD -o $Archive
    if ($LASTEXITCODE -ne 0) { throw "Cannot create candidate ZIP" }
    $Commit = (& git rev-parse HEAD).Trim()
}
finally { Pop-Location }
Expand-Archive -Path $Archive -DestinationPath $Application
$Original = $env:EMBER_DATA_DIR
$env:EMBER_DATA_DIR = $DataDir
$InstallLog = Join-Path $EvidenceRoot "writer-only-install.log"
$QaLog = Join-Path $EvidenceRoot "writer-only-contract.json"
function Invoke-QAProcess([string]$Executable, [string[]]$Arguments, [string]$Log) {
    # Build tools may write nonfatal warnings to stderr even with exit code 0.
    # Start-Process avoids turning those messages into PowerShell exceptions.
    $stderr = "$Log.stderr.log"
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Application -RedirectStandardOutput $Log -RedirectStandardError $stderr -PassThru
    if (-not $process.WaitForExit(300000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "QA process exceeded five-minute stage deadline: $Executable"
    }
    if ($process.ExitCode -ne 0) {
        Get-Content $Log -Tail 20 -ErrorAction SilentlyContinue
        Get-Content $stderr -Tail 20 -ErrorAction SilentlyContinue
        throw "QA child exited with $($process.ExitCode): $Executable"
    }
}
try {
    Push-Location $Application
    try {
        Write-Output "QA_STAGE=Install dependencies (no AI models)"
        Invoke-QAProcess "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\install.ps1", "-SkipModelDownload", "-SkipImageEngineInstall", "-SkipImageModelDownload") $InstallLog
        $Python = Join-Path $Application "backend\.venv\Scripts\python.exe"
        if (-not (Test-Path $Python)) { throw "Installed Python environment missing" }
        if (-not (Test-Path (Join-Path $Application "frontend\node_modules\.bin\vite.cmd"))) { throw "Installed Vite missing" }
        Write-Output "QA_STAGE=Writer offline and verified recovery"
        Invoke-QAProcess $Python @("scripts\qa_writer_only_install.py") $QaLog
        $Source = Join-Path $DataDir "projects\synthetic-fresh-install-qa\manuscript\chapter-001.md"
        if (-not (Test-Path $Source)) { throw "Manuscript not persisted" }
        $Before = (Get-FileHash -Algorithm SHA256 $Source).Hash
        Write-Output "QA_STAGE=Repeat install without replacing manuscript"
        Invoke-QAProcess "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ".\install.ps1", "-SkipModelDownload", "-SkipImageEngineInstall", "-SkipImageModelDownload") (Join-Path $EvidenceRoot "repeat-install.log")
        $After = (Get-FileHash -Algorithm SHA256 $Source).Hash
        if ($Before -ne $After) { throw "Repair unexpectedly modified an author's manuscript" }
        $Report = @{
            schema_version = 1
            synthetic = $true
            exact_commit = $Commit
            source_archive_sha256 = (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLower()
            isolated_install_path = $Application
            isolated_data_path = $DataDir
            installed_writer_without_ai = $true
            manuscript_survived_repeat_install = $true
            backup_restore_tested = $true
            genuinely_fresh_windows_machine = $false
            pinokio_runtime_tested = $false
            beta_release_qualified = $false
            install_log = $InstallLog
            offline_writer_log = $QaLog
        }
        $ReportPath = Join-Path $EvidenceRoot "install-qa-report.json"
        $Report | ConvertTo-Json -Depth 5 | Set-Content -Path $ReportPath -Encoding UTF8
        Write-Output "SAME_HOST_INSTALL_QA_PASSED"
        Write-Output "REPORT=$ReportPath"
        Write-Output "DATA_PRESERVED=$DataDir"
    }
    finally { Pop-Location }
}
finally {
    if ($null -eq $Original) { Remove-Item Env:EMBER_DATA_DIR -ErrorAction SilentlyContinue }
    else { $env:EMBER_DATA_DIR = $Original }
}
