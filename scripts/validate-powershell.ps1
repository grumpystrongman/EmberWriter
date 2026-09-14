$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Files = @(
    (Join-Path $RepoRoot "install.ps1"),
    (Join-Path $RepoRoot "start.ps1"),
    (Join-Path $RepoRoot "start-hosted.ps1"),
    (Join-Path $RepoRoot "scripts\install-image-engine.ps1"),
    (Join-Path $RepoRoot "scripts\start-image-engine.ps1")
)

$failed = $false
foreach ($file in $Files) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $file,
        [ref]$tokens,
        [ref]$errors
    ) | Out-Null

    if ($errors.Count -gt 0) {
        $failed = $true
        Write-Host "PowerShell parse errors in $file" -ForegroundColor Red
        foreach ($errorItem in $errors) {
            Write-Host "  $($errorItem.Message) at $($errorItem.Extent.StartLineNumber):$($errorItem.Extent.StartColumnNumber)" -ForegroundColor Red
        }
    } else {
        Write-Host "PowerShell syntax OK: $file" -ForegroundColor Green
    }
}

if ($failed) { exit 1 }
