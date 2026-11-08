<#
.SYNOPSIS
Start a data-isolated preview of EmberWriter's current author-first features.
.DESCRIPTION
Uses a persistent preview project directory by default. Never points at the
normal author project folder automatically. Refuses to replace an already
running EmberWriter on either standard port.
#>
param(
    [string]$DataDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $DataDir) {
    $DataDir = Join-Path $env:LOCALAPPDATA "EmberWriter\AuthorPreviewData"
}
$Resolved = [System.IO.Path]::GetFullPath($DataDir)
$CheckoutData = [System.IO.Path]::GetFullPath((Join-Path $Root "data"))
if ($Resolved -eq $CheckoutData) {
    throw "Preview data must be in a distinct directory so author work remains protected."
}
foreach ($port in @(8000,5173)) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listeners) {
        throw "Port $port is already serving an app. Close the other EmberWriter window/server before launching this preview. Nothing was stopped."
    }
}
Write-Host ""
Write-Host "EmberWriter | Author-first preview" -ForegroundColor Cyan
Write-Host "Code:    $Root"
Write-Host "Projects: $Resolved"
Write-Host "Your existing books are NOT copied, renamed or overwritten." -ForegroundColor Yellow
Write-Host "AI models remain optional. No weights are downloaded automatically."
Write-Host ""
& (Join-Path $Root "start.ps1") -SkipManagedImageEngine -DataDir $Resolved
