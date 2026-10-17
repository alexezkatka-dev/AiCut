@echo off
rem Stage 0: builds a test CapCut draft. Optional argument: CapCut drafts folder.
setlocal
cd /d "%~dp0"
rem winget puts ffmpeg here; a fresh install may not be on PATH until re-login.
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links;%ProgramFiles%\WinGet\Links"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run install.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m tools.stage0_smoke %*
pause
