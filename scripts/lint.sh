#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

find_python() {
  if [ -x "$repo_root/.venv/Scripts/python.exe" ]; then
    echo "$repo_root/.venv/Scripts/python.exe"
    return
  fi

  if [ -x "$repo_root/.venv/bin/python" ]; then
    echo "$repo_root/.venv/bin/python"
    return
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi

  echo ""
}

find_dotnet() {
  if command -v dotnet >/dev/null 2>&1; then
    command -v dotnet
    return
  fi

  if [ -x "/mnt/c/Program Files/dotnet/dotnet.exe" ]; then
    echo "/mnt/c/Program Files/dotnet/dotnet.exe"
    return
  fi

  if [ -x "/mnt/c/Program Files (x86)/dotnet/dotnet.exe" ]; then
    echo "/mnt/c/Program Files (x86)/dotnet/dotnet.exe"
    return
  fi

  echo ""
}

dotnet_cmd="$(find_dotnet)"
if [ -z "$dotnet_cmd" ]; then
  echo "dotnet was not found on PATH."
  exit 1
fi

python_cmd="$(find_python)"
if [ -z "$python_cmd" ]; then
  echo "Python was not found. Create .venv or install Python before committing."
  exit 1
fi

echo "Running Python lint..."
"$python_cmd" -m ruff check worker/src worker/tests
"$python_cmd" -m ruff format --check worker/src worker/tests

echo "Running .NET lint..."
"$dotnet_cmd" format web/TimelineForVideo.Web.csproj --verify-no-changes --verbosity minimal
"$dotnet_cmd" format tests/TimelineForVideo.E2E/TimelineForVideo.E2E.csproj --verify-no-changes --verbosity minimal
