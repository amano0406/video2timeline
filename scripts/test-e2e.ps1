param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$webProject = Join-Path $repoRoot "web\TimelineForVideo.Web.csproj"
$project = Join-Path $repoRoot "tests\TimelineForVideo.E2E\TimelineForVideo.E2E.csproj"
$e2eOutput = Join-Path ([System.IO.Path]::GetTempPath()) "TimelineForVideo.E2E\bin\"
$testResults = Join-Path $e2eOutput "TestResults"

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

    throw "dotnet was not found on PATH or in Program Files."
}

$dotnet = Resolve-DotNet

Write-Host "Building web project..."
& $dotnet build $webProject
Write-Host "Building E2E project into $e2eOutput..."
& $dotnet build $project -p:OutputPath=$e2eOutput

$playwrightScript = Join-Path $e2eOutput "playwright.ps1"
if (-not (Test-Path $playwrightScript)) {
    throw "Playwright install script not found at $playwrightScript"
}

& $playwrightScript install chromium
$env:TIMELINEFORVIDEO_E2E_REPO_ROOT = $repoRoot
Write-Host "Running E2E tests..."
& $dotnet test $project --no-build -p:OutputPath=$e2eOutput --results-directory $testResults --logger "trx;LogFileName=e2e.trx"
Write-Host "E2E smoke passed. TRX: $(Join-Path $testResults "e2e.trx")"
