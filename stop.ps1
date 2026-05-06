[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$global:LASTEXITCODE = $null

$repoRoot = $PSScriptRoot

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

$docker = Get-TfvDockerCommand
$global:LASTEXITCODE = $null
& $docker compose --project-directory $repoRoot down
exit (Get-TfvLastExitCode)
