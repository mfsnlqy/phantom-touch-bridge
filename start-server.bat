@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%phantom-touch-bridge.exe"
set "CONFIG_PATH=%SCRIPT_DIR%phantom_touch_bridge.toml"
set "EXAMPLE_CONFIG=%SCRIPT_DIR%phantom_touch_bridge.example.toml"
set "SRC_DIR=%SCRIPT_DIR%src"

echo [phantom-touch-bridge] Starting local HTTP bridge...
echo [phantom-touch-bridge] Default HTTP URL: http://127.0.0.1:8765
echo [phantom-touch-bridge] Start Intiface Central first if you plan to use the Intiface backend.
echo [phantom-touch-bridge] Source mode fallback requires Python 3.12.

if not exist "%CONFIG_PATH%" (
  if exist "%EXAMPLE_CONFIG%" (
    copy /Y "%EXAMPLE_CONFIG%" "%CONFIG_PATH%" >nul
    echo [phantom-touch-bridge] Created "%CONFIG_PATH%" from the example config.
  ) else (
    echo [phantom-touch-bridge] WARNING: No config file was found. Built-in defaults will be used.
  )
)

call :select_backend
if "%STARTUP_CANCELLED%"=="1" (
  set "EXIT_CODE=0"
  goto :finish
)
if errorlevel 1 (
  set "EXIT_CODE=1"
  goto :finish
)

if exist "%EXE_PATH%" (
  echo [phantom-touch-bridge] Launching packaged executable with "%SELECTED_BACKEND%" backend...
  if defined CUSTOM_DEVICE_KEYWORD (
    echo [phantom-touch-bridge] Custom mode will try device name keyword: "%CUSTOM_DEVICE_KEYWORD%"
  )
  "%EXE_PATH%" --config "%CONFIG_PATH%" serve
  set "EXIT_CODE=%ERRORLEVEL%"
  goto :finish
)

where py >nul 2>nul
if errorlevel 1 (
  echo [phantom-touch-bridge] ERROR: phantom-touch-bridge.exe was not found.
  echo [phantom-touch-bridge] ERROR: Python launcher "py" is also unavailable.
  set "EXIT_CODE=1"
  goto :finish
)

if exist "%SRC_DIR%" (
  set "PYTHONPATH=%SRC_DIR%;%PYTHONPATH%"
)

echo [phantom-touch-bridge] Packaged executable not found. Falling back to Python source mode with "%SELECTED_BACKEND%" backend...
if defined CUSTOM_DEVICE_KEYWORD (
  echo [phantom-touch-bridge] Custom mode will try device name keyword: "%CUSTOM_DEVICE_KEYWORD%"
)
py -3.12 -m intiface_bridge --config "%CONFIG_PATH%" serve
set "EXIT_CODE=%ERRORLEVEL%"
goto :finish

:select_backend
echo.
echo [phantom-touch-bridge] Choose a backend:
echo   [1] Intiface  - recommended if Intiface Central can see your device
echo   [2] Custom    - try name-based matching for devices not supported by Intiface
echo   [Q] Quit
choice /C 12Q /N /M "Select backend [1/2/Q]: "

if errorlevel 3 (
  echo [phantom-touch-bridge] Startup cancelled by user.
  set "STARTUP_CANCELLED=1"
  exit /b 0
)
if errorlevel 2 goto :configure_custom
if errorlevel 1 goto :configure_intiface

echo [phantom-touch-bridge] Invalid choice.
exit /b 1

:configure_intiface
set "SELECTED_BACKEND=intiface"
set "INTIFACE_BRIDGE_BACKEND_TYPE=intiface"
set "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME="
set "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_ADDRESS="
set "CUSTOM_DEVICE_KEYWORD="
echo [phantom-touch-bridge] Intiface mode selected.
echo [phantom-touch-bridge] Make sure Intiface Central is running before you try /health or connect.
exit /b 0

:configure_custom
set "SELECTED_BACKEND=custom"
set "INTIFACE_BRIDGE_BACKEND_TYPE=custom"
set "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_ADDRESS="
set "CUSTOM_DEVICE_KEYWORD="
set "CONFIG_DEFAULT_DEVICE_NAME="
set "CONFIG_DEFAULT_DEVICE_ADDRESS="
call :load_custom_target_from_config
echo [phantom-touch-bridge] Custom mode selected.
echo [phantom-touch-bridge] You can usually start with a partial device name. MAC address is not required.

:prompt_custom_name
set /P "CUSTOM_DEVICE_KEYWORD=Enter a device name keyword for custom mode: "
if not "%CUSTOM_DEVICE_KEYWORD%"=="" goto :set_custom_name

echo [phantom-touch-bridge] A device name keyword is recommended for custom mode.
set "CUSTOM_NAME_DECISION="
set /P "CUSTOM_NAME_DECISION=Press R to re-enter, or type C to continue without a temporary override [R/C]: "
if /I "%CUSTOM_NAME_DECISION%"=="C" goto :continue_without_custom_name
goto :prompt_custom_name

:set_custom_name
set "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME=%CUSTOM_DEVICE_KEYWORD%"
echo [phantom-touch-bridge] Custom mode will use device name keyword: "%CUSTOM_DEVICE_KEYWORD%"
exit /b 0

:continue_without_custom_name
set "INTIFACE_BRIDGE_BACKEND_DEFAULT_DEVICE_NAME="
set "CUSTOM_DEVICE_KEYWORD="
if defined CONFIG_DEFAULT_DEVICE_NAME goto :continue_with_saved_custom_target
if defined CONFIG_DEFAULT_DEVICE_ADDRESS goto :continue_with_saved_custom_target
echo [phantom-touch-bridge] ERROR: No custom device target was provided.
echo [phantom-touch-bridge] ERROR: Enter a device name keyword, or save default_device_name/default_device_address in phantom_touch_bridge.toml.
choice /C RQ /N /M "Press R to re-enter a device name keyword, or Q to cancel [R/Q]: "
if errorlevel 2 (
  echo [phantom-touch-bridge] Startup cancelled by user.
  set "STARTUP_CANCELLED=1"
  exit /b 0
)
goto :prompt_custom_name

:continue_with_saved_custom_target
echo [phantom-touch-bridge] Continuing without a temporary custom device name.
if defined CONFIG_DEFAULT_DEVICE_NAME (
  echo [phantom-touch-bridge] Using saved custom device name from config: "%CONFIG_DEFAULT_DEVICE_NAME%"
) else (
  echo [phantom-touch-bridge] Using saved custom device address from config.
)
exit /b 0

:load_custom_target_from_config
if not exist "%CONFIG_PATH%" exit /b 0
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /C:"^[ ]*default_device_name[ ]*=" "%CONFIG_PATH%"`) do (
  call :strip_toml_string CONFIG_DEFAULT_DEVICE_NAME "%%B"
  goto :load_custom_target_address
)

:load_custom_target_address
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /C:"^[ ]*default_device_address[ ]*=" "%CONFIG_PATH%"`) do (
  call :strip_toml_string CONFIG_DEFAULT_DEVICE_ADDRESS "%%B"
  goto :load_custom_target_done
)

:load_custom_target_done
exit /b 0

:strip_toml_string
setlocal EnableDelayedExpansion
set "VALUE=%~2"
for /f "tokens=* delims= " %%I in ("!VALUE!") do set "VALUE=%%I"
set "VALUE=!VALUE:"=!"
endlocal & set "%~1=%VALUE%"
exit /b 0

:finish
if not "%EXIT_CODE%"=="0" (
  echo [phantom-touch-bridge] Server exited with code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%
