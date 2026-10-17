@echo off
rem Creates .venv on Python 3.11 and installs pinned dependencies.
setlocal
cd /d "%~dp0"

set "PY="
py -3.11 -c "" >nul 2>&1 && set "PY=py -3.11"
if not defined PY python -c "import sys; sys.exit(sys.version_info[:2] != (3, 11))" >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [ERROR] Python 3.11 not found. Install it from python.org - see docs\PROMPTS.md, step 1.
    goto :fail
)

ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] FFmpeg not found. Run: winget install Gyan.FFmpeg - then close and reopen the window.
    goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating .venv ...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
)

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo [OK] Installed. Next: double-click stage0.bat
pause
exit /b 0

:fail
echo.
echo [FAIL] Copy the text of this window and send it to Claude.
pause
exit /b 1
