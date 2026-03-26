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

set "WEB_PORT=38090"

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /I "%%A"=="VIDEO2TIMELINE_WEB_PORT" set "WEB_PORT=%%B"
)

echo Starting web and worker containers...
set "COMPOSE_GPU_FILE="
where nvidia-smi >nul 2>&1
if not errorlevel 1 (
  set "COMPOSE_GPU_FILE=-f docker-compose.gpu.yml"
  echo NVIDIA GPU detected. Starting worker with GPU support enabled.
)
docker compose -f docker-compose.yml %COMPOSE_GPU_FILE% up --build -d
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
if /I "%VIDEO2TIMELINE_SKIP_BROWSER_OPEN%"=="1" exit /b 0

set "APP_URL=http://localhost:%WEB_PORT%"
set "APP_WINDOW_SIZE=1440,960"
set "APP_BROWSER="
set "APP_BROWSER_NAME="

call :use_default_browser
call :use_browser "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" "Microsoft Edge"
call :use_browser "C:\Program Files\Microsoft\Edge\Application\msedge.exe" "Microsoft Edge"
call :use_browser "C:\Program Files\Google\Chrome\Application\chrome.exe" "Google Chrome"
call :use_browser "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" "Brave"
call :use_browser "C:\Program Files\Chromium\Application\chrome.exe" "Chromium"

if defined APP_BROWSER (
  echo Opening dedicated app window with %APP_BROWSER_NAME%...
  start "" "%APP_BROWSER%" --app="%APP_URL%" --window-size=%APP_WINDOW_SIZE%
  exit /b 0
)

echo No supported Chromium-based app-mode browser was found. Opening the default browser instead.
start "" "%APP_URL%"
exit /b 0

:failed
echo video2timeline did not become ready in time.
echo.
docker compose ps
echo.
echo Last container logs:
docker compose logs --tail 40 web worker
exit /b 1

:use_browser
if defined APP_BROWSER exit /b 0
if exist %~1 (
  set "APP_BROWSER=%~1"
  set "APP_BROWSER_NAME=%~2"
)
exit /b 0

:use_default_browser
if defined APP_BROWSER exit /b 0
for /f "usebackq tokens=1,2 delims=|" %%A in (`powershell -NoLogo -NoProfile -Command "$progId=(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice' -ErrorAction SilentlyContinue).ProgId; if($progId){ $cmd=(Get-ItemProperty ('Registry::HKEY_CLASSES_ROOT\\' + $progId + '\\shell\\open\\command') -ErrorAction SilentlyContinue).'(default)'; if($cmd){ if($cmd -match '\"([^\"]+\\.exe)\"'){ $exe=$Matches[1] } elseif($cmd -match '^([^ ]+\\.exe)'){ $exe=$Matches[1] } if($exe){ $lower=$exe.ToLowerInvariant(); $name=$null; if($lower -like '*\\microsoft\\edge\\application\\msedge.exe'){ $name='Microsoft Edge' } elseif($lower -like '*\\google\\chrome\\application\\chrome.exe'){ $name='Google Chrome' } elseif($lower -like '*\\bravesoftware\\brave-browser\\application\\brave.exe'){ $name='Brave' } elseif($lower -like '*\\chromium\\application\\chrome.exe'){ $name='Chromium' } if($name){ Write-Output ($exe + '|' + $name) } } } }"`) do (
  if not defined APP_BROWSER (
    set "APP_BROWSER=%%~A"
    set "APP_BROWSER_NAME=%%~B"
  )
)
exit /b 0
