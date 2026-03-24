@echo off
setlocal

cd /d "%~dp0"

docker version >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is required and must be running.
  exit /b 1
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
)

set WEB_PORT=8090
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /I "%%A"=="VIDEO2TIMELINE_WEB_PORT" set WEB_PORT=%%B
)

docker compose up --build -d
if errorlevel 1 exit /b 1

start "" "http://localhost:%WEB_PORT%"
