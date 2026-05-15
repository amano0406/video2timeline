[CmdletBinding()]
param(
    [switch]$Build
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$global:LASTEXITCODE = $null

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8NoBom
[Console]::InputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$repoRoot = $PSScriptRoot
. (Join-Path $repoRoot "scripts\runtime.ps1")

$docker = Get-TfvDockerCommand
$runtime = Get-TfvRuntime -RepoRoot $repoRoot -EnsureSettings
$composeArgs = Get-TfvComposeArgs -RepoRoot $repoRoot -EnsureSettings
$computeMode = Get-TfvComputeMode -RepoRoot $repoRoot

Write-Host "Compute mode: $computeMode"
Write-Host "Instance name: $($runtime.InstanceName)"
Write-Host "Compose project: $($runtime.ComposeProject)"
Write-Host "Health API URL: http://127.0.0.1:$($runtime.ApiPort)/health"
Write-Host "Starting TimelineForVideo command worker and health API..."
$global:LASTEXITCODE = $null
$upArgs = @("up", "-d", "--remove-orphans")
if ($Build) {
    $upArgs += "--build"
}
& $docker @composeArgs @upArgs worker health-api
if ((Get-TfvLastExitCode) -ne 0) {
    exit (Get-TfvLastExitCode)
}

Write-Host ""
Write-Host "TimelineForVideo command worker and health API are running."
Write-Host "Processing does not start automatically. Run a CLI processing command when needed."
Write-Host ""
Write-Host "CLI examples:"
Write-Host "  .\cli.ps1 health"
Write-Host "  .\cli.ps1 settings init"
Write-Host "  .\cli.ps1 settings status"
Write-Host "  .\cli.ps1 settings save --input-root C:\apps\Timeline\data\input\video --output-root C:\apps\Timeline\data\to_text\video --compute-mode gpu"
Write-Host "  .\cli.ps1 items refresh --max-items 1"
Write-Host "  .\cli.ps1 process all --max-items 1"
Write-Host "  .\cli.ps1 serve --once --max-items 1"
Write-Host "  .\start.ps1 -Build"
Write-Host ""
Write-Host "Health API:"
Write-Host "  http://127.0.0.1:$($runtime.ApiPort)/health"
Write-Host ""

$global:LASTEXITCODE = $null
& $docker @composeArgs ps
exit (Get-TfvLastExitCode)
