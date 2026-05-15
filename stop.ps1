[CmdletBinding()]
param()

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
$runtime = Get-TfvRuntime -RepoRoot $repoRoot -LegacyIfMissing
$composeArgs = Get-TfvComposeArgs -RepoRoot $repoRoot -LegacyIfMissing

Write-Host "Stopping TimelineForVideo worker and health API..."
Write-Host "Compose project: $($runtime.ComposeProject)"
$global:LASTEXITCODE = $null
& $docker @composeArgs down --remove-orphans
exit (Get-TfvLastExitCode)
