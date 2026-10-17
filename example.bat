@echo off
rem Stage 1: builds a CapCut draft and preview.mp4 from examples\edit_plan.example.json with test clips.
setlocal
cd /d "%~dp0"
rem Reload PATH from the registry: winget may have added a folder since this window opened.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%P;%LOCALAPPDATA%\Microsoft\WinGet\Links;%ProgramFiles%\WinGet\Links"

if not exist ".venv\Scripts\python.exe" goto :no_venv
".venv\Scripts\python.exe" -m tools.stage1_example
pause
exit /b

:no_venv
echo [ERROR] Run install.bat first.
pause
exit /b 1
