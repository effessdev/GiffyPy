@echo off
setlocal enabledelayedexpansion
pushd "%~dp0"

set "FFMPEG_BIN="
where ffmpeg >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where ffmpeg 2^>nul') do (
        set "FFMPEG_BIN=%%~fI"
        goto ffmpeg_ready
    )
)

echo [INFO] FFmpeg not found in PATH.
echo [INFO] FFmpeg is required to build GiffyPy.exe.
choice /M "Install Gyan FFmpeg via winget now"
if errorlevel 2 (
    echo [ERROR] FFmpeg is required but installation was declined.
    popd
    pause
    exit /b 1
)

echo [INFO] Installing Gyan FFmpeg via winget...
winget install --id Gyan.FFmpeg --exact --source winget --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
    echo [ERROR] Failed to install Gyan FFmpeg via winget.
    popd
    pause
    exit /b 1
)

for %%P in (
    "%ProgramFiles%\Gyan\Gyan Dev\FFmpeg\bin\ffmpeg.exe"
    "%ProgramFiles(x86)%\Gyan\Gyan Dev\FFmpeg\bin\ffmpeg.exe"
    "C:\Program Files\Gyan\Gyan Dev\FFmpeg\bin\ffmpeg.exe"
) do (
    if exist "%%~P" set "FFMPEG_BIN=%%~fP"
)

if not defined FFMPEG_BIN (
    for /f "delims=" %%I in ('where /R "%ProgramFiles%" ffmpeg.exe 2^>nul') do (
        echo %%~fI | findstr /I "Gyan\FFmpeg" >nul
        if not errorlevel 1 (
            set "FFMPEG_BIN=%%~fI"
            goto ffmpeg_ready
        )
    )
)

:ffmpeg_ready
if not defined FFMPEG_BIN (
    echo [ERROR] FFmpeg executable not found after installation.
    popd
    pause
    exit /b 1
)

echo [INFO] FFmpeg executable found at: %FFMPEG_BIN%
echo [INFO] You can find the FFmpeg executable here: %FFMPEG_BIN%

set "PYTHON_BIN="
where python >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where python 2^>nul') do (
        set "PYTHON_BIN=%%~fI"
        goto python_ready
    )
)

echo [INFO] Python not found in PATH.
echo [INFO] Python is required to build GiffyPy.exe.
choice /M "Install Python via winget now"
if errorlevel 2 (
    echo [ERROR] Python is required but installation was declined.
    popd
    pause
    exit /b 1
)

echo [INFO] Installing Python via winget...
winget install --id Python.Python.3.12 --exact --source winget --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
    echo [ERROR] Failed to install Python via winget.
    popd
    pause
    exit /b 1
)

for %%P in (
    "%LocalAppData%\Programs\Python\Python312\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles(x86)%\Python312\python.exe"
) do (
    if exist "%%~P" set "PYTHON_BIN=%%~fP"
)

if not defined PYTHON_BIN (
    for /f "delims=" %%I in ('where /R "%LocalAppData%\Programs\Python" python.exe 2^>nul') do (
        set "PYTHON_BIN=%%~fI"
        goto python_ready
    )
)

if not defined PYTHON_BIN (
    for /f "delims=" %%I in ('where /R "%ProgramFiles%" python.exe 2^>nul') do (
        set "PYTHON_BIN=%%~fI"
        goto python_ready
    )
)

:python_ready
if not defined PYTHON_BIN (
    echo [ERROR] Python executable not found after installation.
    echo [ERROR] You may need to restart this script in a new terminal so PATH changes take effect.
    popd
    pause
    exit /b 1
)

echo [INFO] Python executable found at: %PYTHON_BIN%

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found in %~dp0
    popd
    pause
    exit /b 1
)

echo [INFO] Installing dependencies from requirements.txt...
"%PYTHON_BIN%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    popd
    pause
    exit /b 1
)

"%PYTHON_BIN%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies from requirements.txt.
    popd
    pause
    exit /b 1
)

echo [INFO] Checking for PyInstaller...
"%PYTHON_BIN%" -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [INFO] PyInstaller not found. Installing...
    "%PYTHON_BIN%" -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        popd
        pause
        exit /b 1
    )
)

echo [INFO] Starting PyInstaller build...
"%PYTHON_BIN%" -m PyInstaller --clean --noconfirm GiffyPy.spec
if errorlevel 1 (
    popd
    pause
    exit /b %errorlevel%
)

set "SHORTCUT_SCRIPT_SRC=%~dp0scripts\create_shortcut.bat"
set "DIST_DIR=%~dp0dist\GiffyPy"
set "EXE_PATH=%DIST_DIR%\GiffyPy.exe"

if not exist "%SHORTCUT_SCRIPT_SRC%" (
    echo [ERROR] create_shortcut.bat not found at: %SHORTCUT_SCRIPT_SRC%
    popd
    pause
    exit /b 1
)

if not exist "%DIST_DIR%" (
    echo [ERROR] Dist folder not found at: %DIST_DIR%
    popd
    pause
    exit /b 1
)

echo [INFO] Copying create_shortcut.bat to dist\GiffyPy...
copy /Y "%SHORTCUT_SCRIPT_SRC%" "%DIST_DIR%\create_shortcut.bat" >nul
if errorlevel 1 (
    echo [ERROR] Failed to copy create_shortcut.bat to dist\GiffyPy.
    popd
    pause
    exit /b 1
)

if not exist "%EXE_PATH%" (
    echo [ERROR] Build finished but GiffyPy.exe was not found at: %EXE_PATH%
    popd
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   BUILD COMPLETE
echo ========================================================
echo.
echo   GiffyPy.exe is ready at:
echo.
echo     %EXE_PATH%
echo.
echo   To create a Start Menu shortcut, run create_shortcut.bat
echo   from inside that same folder:
echo.
echo     %DIST_DIR%\create_shortcut.bat
echo.
echo ========================================================
echo.

popd
pause
endlocal
