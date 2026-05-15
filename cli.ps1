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
. (Join-Path $repoRoot "scripts\runtime.ps1")

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
$composeArgs = Get-TfvComposeArgs -RepoRoot $repoRoot -EnsureSettings

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
