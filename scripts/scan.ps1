param(
    [string]$Config = "C:\apps\video2timeline\configs\local.json",
    [string]$Output = "C:\apps\video2timeline\runs\discovery.json"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$env:PYTHONPATH = Join-Path $root "worker\src"

& $python -m video2timeline_worker scan --config $Config --output $Output
