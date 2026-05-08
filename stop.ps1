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
if (-not $env:TIMELINE_FOR_VIDEO_C_DRIVE_MOUNT) {
    $env:TIMELINE_FOR_VIDEO_C_DRIVE_MOUNT = "C:\"
}
if (-not $env:TIMELINE_FOR_VIDEO_F_DRIVE_MOUNT) {
    $env:TIMELINE_FOR_VIDEO_F_DRIVE_MOUNT = "F:\"
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

function Get-TfvComputeMode {
    $settingsPath = Join-Path $repoRoot "settings.json"
    if (-not (Test-Path -LiteralPath $settingsPath)) {
        return "gpu"
    }

    try {
        $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
        $mode = [string]$settings.computeMode
        if ($mode.ToLowerInvariant() -eq "gpu") {
            return "gpu"
        }
    } catch {
        return "gpu"
    }

    return "gpu"
}

function Get-TfvComposeArgs {
    $args = @("compose", "--project-directory", $repoRoot)
    if ((Get-TfvComputeMode) -eq "gpu") {
        $args += @("-f", (Join-Path $repoRoot "docker-compose.yml"))
        $args += @("-f", (Join-Path $repoRoot "docker-compose.gpu.yml"))
    }
    return $args
}

$docker = Get-TfvDockerCommand
$composeArgs = Get-TfvComposeArgs

Write-Host "Stopping TimelineForVideo worker..."
$global:LASTEXITCODE = $null
& $docker @composeArgs down --remove-orphans
exit (Get-TfvLastExitCode)
