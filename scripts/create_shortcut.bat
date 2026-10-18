@echo off
setlocal enabledelayedexpansion
pushd "%~dp0"

set "EXE_PATH=%~dp0GiffyPy.exe"
set "SHORTCUT_NAME=GiffyPy.lnk"
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
set "SHORTCUT_PATH=%START_MENU%\%SHORTCUT_NAME%"

if not exist "%EXE_PATH%" (
    echo [ERROR] GiffyPy.exe not found at: %EXE_PATH%
    popd
    pause
    exit /b 1
)

echo [INFO] Creating shortcut at: %SHORTCUT_PATH%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$sc = $ws.CreateShortcut('%SHORTCUT_PATH%');" ^
    "$sc.TargetPath = '%EXE_PATH%';" ^
    "$sc.WorkingDirectory = '%~dp0';" ^
    "$sc.IconLocation = '%EXE_PATH%,0';" ^
    "$sc.Description = 'Launch GiffyPy';" ^
    "$sc.Save()"

if errorlevel 1 (
    echo [ERROR] Failed to create shortcut.
    popd
    pause
    exit /b 1
)

if not exist "%SHORTCUT_PATH%" (
    echo [ERROR] Shortcut creation reported success but file not found.
    popd
    pause
    exit /b 1
)

echo.
echo.
echo   ============================================================
echo.
echo   [INFO] Shortcut created successfully.
echo   [INFO] GiffyPy should now be searchable from the Start Menu.
echo.
echo   ------------------------------------------------------------
echo.
echo   [NOTE] This only created a shortcut - it does NOT copy GiffyPy.exe.
echo   [NOTE] Do not move or delete this folder, or GiffyPy.exe inside it,
echo   [NOTE] or the shortcut will stop working.
echo.
echo   ============================================================
echo.

popd
pause
endlocal
