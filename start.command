#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop is required and must be running."
  exit 1
fi

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
fi

WEB_PORT="$(grep -E '^VIDEO2TIMELINE_WEB_PORT=' .env | tail -n 1 | cut -d'=' -f2)"
if [ -z "${WEB_PORT}" ]; then
  WEB_PORT="8090"
fi

docker compose up --build -d
open "http://localhost:${WEB_PORT}"
