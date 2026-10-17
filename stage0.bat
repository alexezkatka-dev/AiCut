@echo off
rem Stage 0: builds a test CapCut draft. Optional argument: CapCut drafts folder.
setlocal
cd /d "%~dp0"
rem Reload PATH from the registry: winget may have added a folder since this window opened.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%P;%LOCALAPPDATA%\Microsoft\WinGet\Links;%ProgramFiles%\WinGet\Links"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run install.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m tools.stage0_smoke %*
pause
