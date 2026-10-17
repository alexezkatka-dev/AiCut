@echo off
rem Stage 2: text search over the samples index. Without an argument asks for queries one by one.
setlocal
cd /d "%~dp0"
rem Reload PATH from the registry: winget may have added a folder since this window opened.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%P;%LOCALAPPDATA%\Microsoft\WinGet\Links;%ProgramFiles%\WinGet\Links"

if not exist ".venv\Scripts\python.exe" goto :no_venv
".venv\Scripts\python.exe" -m autoedit.cli search %* --project samples
pause
exit /b

:no_venv
echo [ERROR] Run install.bat first.
pause
exit /b 1
