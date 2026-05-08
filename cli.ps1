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

function Test-TfvWorkerRunning {
    param(
        [string]$Docker,
        [string[]]$ComposeArgs
    )

    $global:LASTEXITCODE = $null
    $services = @(& $Docker @ComposeArgs ps --status running --services 2>$null)
    if ((Get-TfvLastExitCode) -ne 0) {
        return $false
    }

    return $services -contains "worker"
}

function Start-TfvWorker {
    param(
        [string]$Docker,
        [string[]]$ComposeArgs
    )

    $global:LASTEXITCODE = $null
    & $Docker @ComposeArgs up -d --no-deps worker
    if ((Get-TfvLastExitCode) -ne 0) {
        exit (Get-TfvLastExitCode)
    }
}

function Wait-TfvWorkerRunning {
    param(
        [string]$Docker,
        [string[]]$ComposeArgs
    )

    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-TfvWorkerRunning -Docker $Docker -ComposeArgs $ComposeArgs) {
            return $true
        }
        Start-Sleep -Seconds 1
    }

    return $false
}

$docker = Get-TfvDockerCommand
$composeArgs = Get-TfvComposeArgs

if (-not (Test-TfvWorkerRunning -Docker $docker -ComposeArgs $composeArgs)) {
    Start-TfvWorker -Docker $docker -ComposeArgs $composeArgs
    if (-not (Wait-TfvWorkerRunning -Docker $docker -ComposeArgs $composeArgs)) {
        Write-Error "TimelineForVideo worker did not reach running state."
        exit 1
    }
}

$global:LASTEXITCODE = $null
& $docker @composeArgs exec -T worker python -m timeline_for_video_worker @CliArgs
exit (Get-TfvLastExitCode)
