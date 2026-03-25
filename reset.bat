@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

for %%I in ("%CD%") do set "COMPOSE_PROJECT=%%~nI"
set "APPDATA_VOLUME=%COMPOSE_PROJECT%_app-data"
set "OUTPUTS_VOLUME=%COMPOSE_PROJECT%_outputs"
set "UPLOADS_VOLUME=%COMPOSE_PROJECT%_uploads"
set "HF_CACHE_VOLUME=%COMPOSE_PROJECT%_hf-cache"
set "TORCH_CACHE_VOLUME=%COMPOSE_PROJECT%_torch-cache"

set "AUTO_CONFIRM=false"
set "AUTO_DELETE_ENV=false"
set "AUTO_DELETE_APPDATA=false"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--yes" (
  set "AUTO_CONFIRM=true"
  shift
  goto parse_args
)
if /I "%~1"=="--delete-env" (
  set "AUTO_DELETE_ENV=true"
  shift
  goto parse_args
)
if /I "%~1"=="--delete-appdata" (
  set "AUTO_DELETE_APPDATA=true"
  shift
  goto parse_args
)
echo Unknown option: %~1
echo Supported options: --yes --delete-env --delete-appdata
exit /b 1

:args_done

where docker >nul 2>&1
if errorlevel 1 (
  echo docker.exe was not found on PATH.
  echo Install Docker Desktop first, then try again.
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is installed but the Docker engine is not ready.
  echo Start Docker Desktop and wait until the engine is running, then try again.
  exit /b 1
)

echo.
echo video2timeline reset
echo.
echo This will remove:
echo   - Docker containers for this project
echo   - Docker images built for this project
echo   - temporary Docker volumes for this project
echo   - Docker network for this project
echo.
echo Optional:
echo   - delete saved app data volume ^(includes token and settings^)
if exist ".env" (
  echo   - delete local .env
)
echo.

if /I not "%AUTO_CONFIRM%"=="true" (
  set /p "RESET_CONFIRM=Type RESET to continue: "
  if /I not "!RESET_CONFIRM!"=="RESET" (
    echo Reset canceled.
    exit /b 1
  )
)

echo.
echo Stopping and removing Docker resources...
docker compose -f docker-compose.yml -f docker-compose.gpu.yml down --rmi local --remove-orphans
if errorlevel 1 (
  echo Docker cleanup failed.
  exit /b 1
)

call :remove_volume_if_exists "!UPLOADS_VOLUME!"
if errorlevel 1 exit /b 1
call :remove_volume_if_exists "!OUTPUTS_VOLUME!"
if errorlevel 1 exit /b 1
call :remove_volume_if_exists "!HF_CACHE_VOLUME!"
if errorlevel 1 exit /b 1
call :remove_volume_if_exists "!TORCH_CACHE_VOLUME!"
if errorlevel 1 exit /b 1

if /I "%AUTO_DELETE_APPDATA%"=="true" (
  call :remove_volume_if_exists "!APPDATA_VOLUME!"
  if errorlevel 1 exit /b 1
  echo Deleted saved app data volume.
) else (
  echo.
  echo Saved app data volume:
  echo   !APPDATA_VOLUME!
  echo This includes your saved Hugging Face token and app settings.
  set /p "DELETE_APPDATA_CONFIRM=Delete saved token and settings too? Type DELETE_DATA to confirm or press Enter to keep them: "
  if /I "!DELETE_APPDATA_CONFIRM!"=="DELETE_DATA" (
    call :remove_volume_if_exists "!APPDATA_VOLUME!"
    if errorlevel 1 exit /b 1
    echo Deleted saved app data volume.
  ) else (
    echo Kept saved token and settings.
  )
)

echo Docker resources removed.

if exist ".env" (
  if /I "%AUTO_DELETE_ENV%"=="true" (
    del /q ".env"
    echo Deleted .env
  ) else (
    echo.
    set /p "DELETE_ENV_CONFIRM=Delete local .env as well? Type DELETE_ENV to confirm or press Enter to keep it: "
    if /I "!DELETE_ENV_CONFIRM!"=="DELETE_ENV" (
      del /q ".env"
      echo Deleted .env
    ) else (
      echo Kept .env
    )
  )
)

echo.
echo Reset completed.
exit /b 0

:remove_volume_if_exists
set "VOLUME_NAME=%~1"
if not defined VOLUME_NAME exit /b 0

for /f %%V in ('docker volume ls --format "{{.Name}}" ^| findstr /I /X /C:"%VOLUME_NAME%"') do (
  docker volume rm "%%V" >nul
  if errorlevel 1 (
    echo Failed to remove Docker volume: %%V
    exit /b 1
  )
  echo Removed Docker volume: %%V
)

exit /b 0
