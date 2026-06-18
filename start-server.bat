@echo off
setlocal EnableExtensions

cd /d "%~dp0"
title phantom-touch-bridge

set "BACKEND_TYPE="
set "BACKEND_DEVICE_NAME="
set "HEART_RATE_ENABLED=false"
set "HEART_RATE_DEVICE_NAME="
set "HEART_RATE_DEVICE_ADDRESS="
set "PYTHON_CMD="
set "LAUNCH_MODE="
set "LAUNCH_CMD="
set "REPO_SRC=%~dp0src"

:select_backend
cls
echo ========================================
echo phantom-touch-bridge
echo ========================================
echo.
echo Select control backend:
echo   [1] Intiface
echo   [2] custom
echo   [Q] Quit
echo.
choice /c 12Q /n /m "Choice: "
if errorlevel 3 goto :quit
if errorlevel 2 (
    set "BACKEND_TYPE=custom"
    goto :prompt_backend_target
)
if errorlevel 1 (
    set "BACKEND_TYPE=intiface"
    set "BACKEND_DEVICE_NAME="
    goto :select_heart_rate
)
goto :select_backend

:prompt_backend_target
cls
echo ========================================
echo Custom Device Target
echo ========================================
echo.
echo Enter a device name keyword for custom mode.
echo Partial names are allowed.
echo.
set "BACKEND_DEVICE_NAME="
set "BACKEND_DEVICE_NAME_CHECK="
set /p "BACKEND_DEVICE_NAME=Custom device name keyword: "
for /f "tokens=* delims= " %%A in ("%BACKEND_DEVICE_NAME%") do set "BACKEND_DEVICE_NAME_CHECK=%%A"
if defined BACKEND_DEVICE_NAME_CHECK goto :select_heart_rate
echo.
echo Please provide a device name keyword for custom mode.
echo.
pause
goto :prompt_backend_target

:select_heart_rate
cls
echo ========================================
echo phantom-touch-bridge
echo ========================================
echo.
echo Heart rate input:
echo   [1] Disabled
echo   [2] Enabled
echo   [Q] Quit
echo.
choice /c 12Q /n /m "Choice: "
if errorlevel 3 goto :quit
if errorlevel 2 (
    set "HEART_RATE_ENABLED=true"
    goto :prompt_heart_rate_target
)
if errorlevel 1 (
    set "HEART_RATE_ENABLED=false"
    set "HEART_RATE_DEVICE_NAME="
    set "HEART_RATE_DEVICE_ADDRESS="
    goto :resolve_launcher
)
goto :select_heart_rate

:prompt_heart_rate_target
cls
echo ========================================
echo Heart Rate Target
echo ========================================
echo.
echo Enter a band name keyword for heart rate input.
echo.
set "HEART_RATE_DEVICE_NAME="
set "HEART_RATE_DEVICE_ADDRESS="
set "HEART_RATE_DEVICE_NAME_CHECK="
set /p "HEART_RATE_DEVICE_NAME=Band name keyword: "
for /f "tokens=* delims= " %%A in ("%HEART_RATE_DEVICE_NAME%") do set "HEART_RATE_DEVICE_NAME_CHECK=%%A"
if defined HEART_RATE_DEVICE_NAME_CHECK goto :resolve_launcher
set "HEART_RATE_DEVICE_ADDRESS="
echo.
echo Please provide a band name keyword.
echo.
pause
goto :prompt_heart_rate_target

:resolve_launcher
if exist ".\phantom-touch-bridge.exe" (
    set "LAUNCH_MODE=exe"
    set "LAUNCH_CMD=".\phantom-touch-bridge.exe""
    goto :launch
)

if exist ".\intiface-bridge.exe" (
    set "LAUNCH_MODE=exe"
    set "LAUNCH_CMD=".\intiface-bridge.exe""
    goto :launch
)

if exist ".\intiface_bridge.exe" (
    set "LAUNCH_MODE=exe"
    set "LAUNCH_CMD=".\intiface_bridge.exe""
    goto :launch
)

if exist ".\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=".\.venv\Scripts\python.exe""
    set "LAUNCH_MODE=python"
    goto :launch
)

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    set "LAUNCH_MODE=python"
    goto :launch
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    set "LAUNCH_MODE=python"
    goto :launch
)

echo.
echo Python was not found. Install Python or create .venv first.
echo.
pause
goto :quit

:launch
cls
echo ========================================
echo Starting phantom-touch-bridge
echo ========================================
echo.
echo Current mode:
echo - Control backend: %BACKEND_TYPE%
if defined BACKEND_DEVICE_NAME (
    call echo - Control device keyword: %%BACKEND_DEVICE_NAME%%
)
if /i "%HEART_RATE_ENABLED%"=="true" (
    echo - Heart rate input: enabled
    if defined HEART_RATE_DEVICE_NAME (
        call echo - Band name keyword: %%HEART_RATE_DEVICE_NAME%%
    ) else (
        echo - Band name keyword: ^<empty^>
    )
) else (
    echo - Heart rate input: disabled
)
echo.
echo The service is starting in this window.
echo Press Ctrl+C here if you want to stop it later.
echo.

if defined INTIFACE_BRIDGE_START_SERVER_DRY_RUN (
    echo [dry-run] INTIFACE_BRIDGE_BACKEND_TYPE=%BACKEND_TYPE%
    call echo [dry-run] INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME=%%BACKEND_DEVICE_NAME%%
    echo [dry-run] INTIFACE_BRIDGE_HEART_RATE_ENABLED=%HEART_RATE_ENABLED%
    call echo [dry-run] INTIFACE_BRIDGE_HEART_RATE_DEVICE_NAME=%%HEART_RATE_DEVICE_NAME%%
    call echo [dry-run] INTIFACE_BRIDGE_HEART_RATE_DEVICE_ADDRESS=%%HEART_RATE_DEVICE_ADDRESS%%
    echo [dry-run] launch_mode=%LAUNCH_MODE%
    if /i "%LAUNCH_MODE%"=="exe" (
        echo [dry-run] %LAUNCH_CMD% serve
    ) else (
        echo [dry-run] %PYTHON_CMD% -m intiface_bridge serve
    )
    echo.
    pause
    goto :quit
)

call set "BACKEND_DEVICE_NAME_ENV=%%BACKEND_DEVICE_NAME%%"
if not defined BACKEND_DEVICE_NAME_ENV set "BACKEND_DEVICE_NAME_ENV= "
call set "HEART_RATE_DEVICE_NAME_ENV=%%HEART_RATE_DEVICE_NAME%%"
if not defined HEART_RATE_DEVICE_NAME_ENV set "HEART_RATE_DEVICE_NAME_ENV= "
set "HEART_RATE_DEVICE_ADDRESS_ENV= "

set "INTIFACE_BRIDGE_BACKEND_TYPE=%BACKEND_TYPE%"
set "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME=%BACKEND_DEVICE_NAME_ENV%"
set "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_ADDRESS= "
set "INTIFACE_BRIDGE_HEART_RATE_ENABLED=%HEART_RATE_ENABLED%"
set "INTIFACE_BRIDGE_HEART_RATE_DEVICE_NAME=%HEART_RATE_DEVICE_NAME_ENV%"
set "INTIFACE_BRIDGE_HEART_RATE_DEVICE_ADDRESS=%HEART_RATE_DEVICE_ADDRESS_ENV%"
if /i "%LAUNCH_MODE%"=="exe" (
    call %LAUNCH_CMD% serve
) else (
    if defined PYTHONPATH (
        set "PYTHONPATH=%REPO_SRC%;%PYTHONPATH%"
    ) else (
        set "PYTHONPATH=%REPO_SRC%"
    )
    call %PYTHON_CMD% -m intiface_bridge serve
)
echo.
pause
goto :quit

:quit
endlocal
exit /b 0

