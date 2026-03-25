@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not installed or docker.exe is not on PATH.
  echo Install Docker Desktop, start it, and try again.
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is installed but the Docker engine is not ready.
  echo Start Docker Desktop and wait until it shows the engine is running, then try again.
  exit /b 1
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example.
)

set "VIDEO_SOURCE_1="
set "VIDEO_SOURCE_2="
set "VIDEO_OUTPUT_ROOT="
set "WEB_PORT=38090"

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /I "%%A"=="VIDEO_SOURCE_1" set "VIDEO_SOURCE_1=%%B"
  if /I "%%A"=="VIDEO_SOURCE_2" set "VIDEO_SOURCE_2=%%B"
  if /I "%%A"=="VIDEO_OUTPUT_ROOT" set "VIDEO_OUTPUT_ROOT=%%B"
  if /I "%%A"=="VIDEO2TIMELINE_WEB_PORT" set "WEB_PORT=%%B"
)

call :validate_input_path "VIDEO_SOURCE_1" "!VIDEO_SOURCE_1!"
if errorlevel 1 exit /b 1

call :validate_input_path "VIDEO_SOURCE_2" "!VIDEO_SOURCE_2!"
if errorlevel 1 exit /b 1

call :validate_output_path "VIDEO_OUTPUT_ROOT" "!VIDEO_OUTPUT_ROOT!"
if errorlevel 1 exit /b 1

echo Starting web and worker containers...
docker compose up --build -d
if errorlevel 1 (
  echo docker compose failed before the app became ready.
  exit /b 1
)

echo Waiting for containers and web health check...
set /a ATTEMPT=0

:wait_loop
set /a ATTEMPT+=1
set "WEB_RUNNING="
set "WORKER_RUNNING="

for /f %%S in ('docker compose ps --services --status running 2^>nul') do (
  if /I "%%S"=="web" set "WEB_RUNNING=1"
  if /I "%%S"=="worker" set "WORKER_RUNNING=1"
)

if defined WEB_RUNNING if defined WORKER_RUNNING (
  powershell -NoLogo -NoProfile -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:%WEB_PORT%' -UseBasicParsing -TimeoutSec 5; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 goto ready
)

if !ATTEMPT! GEQ 45 goto failed

timeout /t 2 /nobreak >nul
goto wait_loop

:ready
echo video2timeline is ready at http://localhost:%WEB_PORT%
start "" "http://localhost:%WEB_PORT%"
exit /b 0

:failed
echo video2timeline did not become ready in time.
echo.
docker compose ps
echo.
echo Last container logs:
docker compose logs --tail 40 web worker
exit /b 1

:validate_input_path
set "VAR_NAME=%~1"
set "VAR_VALUE=%~2"

if not defined VAR_VALUE (
  echo %VAR_NAME% is not set in .env.
  exit /b 1
)

echo %VAR_VALUE% | findstr /I /C:":\path\to\" /C:"/path/to/" >nul
if not errorlevel 1 (
  echo %VAR_NAME% still uses the placeholder value in .env.
  echo Edit .env and set it to a real directory before starting.
  exit /b 1
)

if not exist "%VAR_VALUE%" (
  echo %VAR_NAME% does not exist: %VAR_VALUE%
  exit /b 1
)

exit /b 0

:validate_output_path
set "VAR_NAME=%~1"
set "VAR_VALUE=%~2"

if not defined VAR_VALUE (
  echo %VAR_NAME% is not set in .env.
  exit /b 1
)

echo %VAR_VALUE% | findstr /I /C:":\path\to\" /C:"/path/to/" >nul
if not errorlevel 1 (
  echo %VAR_NAME% still uses the placeholder value in .env.
  echo Edit .env and set it to a real directory before starting.
  exit /b 1
)

if not exist "%VAR_VALUE%" (
  echo Creating output directory: %VAR_VALUE%
  mkdir "%VAR_VALUE%" >nul 2>&1
  if errorlevel 1 (
    echo Failed to create output directory: %VAR_VALUE%
    exit /b 1
  )
)

exit /b 0
