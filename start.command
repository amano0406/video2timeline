#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop is not installed or docker is not on PATH."
  echo "Install Docker Desktop, start it, and try again."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop is installed but the Docker engine is not ready."
  echo "Start Docker Desktop and wait until the engine is running, then try again."
  exit 1
fi

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example."
fi

read_env_value() {
  local key="$1"
  grep -E "^${key}=" .env | tail -n 1 | cut -d'=' -f2-
}

WEB_PORT="$(read_env_value VIDEO2TIMELINE_WEB_PORT)"
if [ -z "${WEB_PORT}" ]; then
  WEB_PORT="38090"
fi

echo "Starting web and worker containers..."
compose_args=(-f docker-compose.yml)
if command -v nvidia-smi >/dev/null 2>&1; then
  compose_args+=(-f docker-compose.gpu.yml)
  echo "NVIDIA GPU detected. Starting worker with GPU support enabled."
fi
docker compose "${compose_args[@]}" up --build -d

echo "Waiting for containers and web health check..."
for _ in $(seq 1 45); do
  running_services="$(docker compose ps --services --status running || true)"
  if echo "$running_services" | grep -qx "web" && echo "$running_services" | grep -qx "worker"; then
    if curl -fsS "http://localhost:${WEB_PORT}" >/dev/null 2>&1; then
      echo "video2timeline is ready at http://localhost:${WEB_PORT}"
      open "http://localhost:${WEB_PORT}"
      exit 0
    fi
  fi
  sleep 2
done

echo "video2timeline did not become ready in time."
echo
docker compose ps || true
echo
echo "Last container logs:"
docker compose logs --tail 40 web worker || true
exit 1
