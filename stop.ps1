[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

$docker = Get-TfvDockerCommand
& $docker compose --project-directory $repoRoot down
exit $LASTEXITCODE
