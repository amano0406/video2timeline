[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$global:LASTEXITCODE = $null

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

function Get-TfvLastExitCode {
    if ($null -eq $global:LASTEXITCODE) {
        return 1
    }

    return [int]$global:LASTEXITCODE
}

function Test-TfvWorkerRunning {
    param([string]$Docker)

    $global:LASTEXITCODE = $null
    $services = @(& $Docker compose --project-directory $repoRoot ps --status running --services 2>$null)
    if ((Get-TfvLastExitCode) -ne 0) {
        return $false
    }

    return $services -contains "worker"
}

$docker = Get-TfvDockerCommand

if (Test-TfvWorkerRunning -Docker $docker) {
    $global:LASTEXITCODE = $null
    & $docker compose --project-directory $repoRoot exec -T worker python -m timeline_for_video_worker @CliArgs
    exit (Get-TfvLastExitCode)
}

$global:LASTEXITCODE = $null
& $docker compose --project-directory $repoRoot build worker
if ((Get-TfvLastExitCode) -ne 0) {
    exit (Get-TfvLastExitCode)
}

$global:LASTEXITCODE = $null
& $docker compose --project-directory $repoRoot run --rm --no-deps worker @CliArgs
exit (Get-TfvLastExitCode)
