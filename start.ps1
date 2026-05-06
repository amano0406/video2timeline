[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8NoBom
[Console]::InputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$repoRoot = $PSScriptRoot
if (-not $env:TIMELINE_FOR_VIDEO_C_DRIVE_MOUNT) {
    $env:TIMELINE_FOR_VIDEO_C_DRIVE_MOUNT = "C:\"
}

function Get-TfvDockerCommand {
    $dockerExe = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $dockerExe) { return $dockerExe }

    $docker = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($docker) { return $docker.Source }

    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) { return $docker.Source }

    throw "docker.exe was not found. Install or start Docker Desktop."
}

$docker = Get-TfvDockerCommand

Write-Host "Starting TimelineForVideo worker..."
& $docker compose --project-directory $repoRoot up -d --build
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "TimelineForVideo worker is running."
Write-Host ""
Write-Host "CLI examples:"
Write-Host "  .\cli.ps1 health"
Write-Host "  .\cli.ps1 settings init"
Write-Host "  .\cli.ps1 settings status"
Write-Host "  .\cli.ps1 settings save --input-root C:\TimelineData\input-video --output-root C:\TimelineData\video"
Write-Host ""

& $docker compose --project-directory $repoRoot ps
exit $LASTEXITCODE
