@echo off
rem Stage 2: indexes the takes in samples\footage (or the folder given as the argument).
setlocal
cd /d "%~dp0"
rem Reload PATH from the registry: winget may have added a folder since this window opened.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%P;%LOCALAPPDATA%\Microsoft\WinGet\Links;%ProgramFiles%\WinGet\Links"

if not exist ".venv\Scripts\python.exe" goto :no_venv
set "FOLDER=%~1"
if not defined FOLDER set "FOLDER=samples\footage"
".venv\Scripts\python.exe" -m autoedit.cli index "%FOLDER%" --project samples
pause
exit /b

:no_venv
echo [ERROR] Run install.bat first.
pause
exit /b 1
