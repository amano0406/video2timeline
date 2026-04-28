param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Resolve-Python {
    $windowsVenv = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path $windowsVenv) {
        return $windowsVenv
    }

    $unixVenv = Join-Path $repoRoot ".venv/bin/python"
    if (Test-Path $unixVenv) {
        return $unixVenv
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Python was not found. Create .venv or install Python before linting."
}

function Resolve-DotNet {
    $dotnetCommand = Get-Command dotnet -ErrorAction SilentlyContinue
    if ($dotnetCommand) {
        return $dotnetCommand.Source
    }

    $programFilesDotNet = Join-Path ${env:ProgramFiles} "dotnet\dotnet.exe"
    if (Test-Path $programFilesDotNet) {
        return $programFilesDotNet
    }

    $programFilesX86DotNet = Join-Path ${env:ProgramFiles(x86)} "dotnet\dotnet.exe"
    if (Test-Path $programFilesX86DotNet) {
        return $programFilesX86DotNet
    }

    throw "dotnet was not found on PATH."
}

$python = Resolve-Python
$dotnet = Resolve-DotNet

Write-Host "Running Python lint..."
Invoke-CheckedCommand $python -m ruff check worker/src worker/tests
Invoke-CheckedCommand $python -m ruff format --check worker/src worker/tests

Write-Host "Running .NET lint..."
Invoke-CheckedCommand $dotnet format web/TimelineForVideo.Web.csproj --verify-no-changes --verbosity minimal
Invoke-CheckedCommand $dotnet format tests/TimelineForVideo.E2E/TimelineForVideo.E2E.csproj --verify-no-changes --verbosity minimal
