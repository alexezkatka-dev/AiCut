@echo off
rem Creates .venv on Python 3.11 and installs pinned dependencies.
rem If Python 3.11 or FFmpeg is missing, offers to install it with winget.
rem No multi-line ( ) blocks: paths with ")" would break them.
setlocal
cd /d "%~dp0"
call :refresh_path

rem ---------- Python 3.11 ----------
call :find_python
if defined PY goto :python_ok
echo Python 3.11 not found. Python found on this computer:
call :list_pythons
call :offer_winget Python.Python.3.11 "Python 3.11"
call :refresh_path
call :find_python
if defined PY goto :python_ok
echo.
echo [ERROR] Python 3.11 not found.
echo Install Python 3.11.9 by hand - "Windows installer 64-bit" on this page:
echo   https://www.python.org/downloads/release/python-3119/
echo Do not use the big button on python.org - it gives a newer version.
echo In the installer tick "Add python.exe to PATH". Then run install.bat again.
goto :fail
:python_ok
echo Python 3.11: %PY%

rem ---------- FFmpeg ----------
ffmpeg -version >nul 2>&1
if not errorlevel 1 goto :ffmpeg_ok
echo FFmpeg not found.
call :offer_winget Gyan.FFmpeg "FFmpeg"
call :refresh_path
ffmpeg -version >nul 2>&1
if not errorlevel 1 goto :ffmpeg_ok
echo.
echo [ERROR] FFmpeg not found.
echo If winget said FFmpeg was installed, close this window and run install.bat again.
echo Otherwise in PowerShell run:  winget install -e --id Gyan.FFmpeg  and then run install.bat again.
goto :fail
:ffmpeg_ok
echo FFmpeg: OK

rem ---------- .venv + packages ----------
rem Reuse .venv only if it is Python 3.11 with pip; a half-made or wrong one is rebuilt.
if not exist ".venv" goto :make_venv
".venv\Scripts\python.exe" -c "import sys, pip; sys.exit(sys.version_info[:2] != (3, 11))" <nul >nul 2>&1 && goto :venv_ok
echo Existing .venv is broken or not Python 3.11 - recreating it ...
rmdir /s /q ".venv"
if exist ".venv" echo [ERROR] Could not delete .venv - close other windows that use it, then run install.bat again.
if exist ".venv" goto :fail
:make_venv
echo Creating .venv ...
%PY% -m venv .venv
if errorlevel 1 goto :fail
:venv_ok
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo [OK] Installed.
pause
exit /b 0

:fail
echo.
echo [FAIL] Copy the text of this window and send it to Claude.
pause
exit /b 1

rem ================= subroutines =================

:find_python
rem Sets PY to a command that runs Python 3.11, or leaves it undefined.
set "PY="
echo Checking for Python 3.11 - the first check may take a minute ...
py -3.11 -c "" <nul >nul 2>&1 && set "PY=py -3.11"
if defined PY exit /b 0
call :try_python "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if defined PY exit /b 0
call :try_python "%ProgramFiles%\Python311\python.exe"
if defined PY exit /b 0
call :try_python "python"
exit /b 0

:try_python
"%~1" -c "import sys; sys.exit(sys.version_info[:2] != (3, 11))" <nul >nul 2>&1 && set PY="%~1"
exit /b 0

:list_pythons
py -0p <nul 2>nul || echo   - no py launcher
where python 2>nul || echo   - no python on PATH
exit /b 0

:offer_winget
rem %1 = winget package id, %2 = name shown to the user. Digits work with any keyboard layout.
where winget >nul 2>&1 || goto :no_winget
echo.
choice /c 12 /m "Install %~2 now with winget? 1 = yes, 2 = no"
if errorlevel 2 exit /b 1
winget install -e --id %~1 --accept-package-agreements --accept-source-agreements
exit /b 0

:no_winget
echo.
echo winget is not available on this PC, so %~2 cannot be installed automatically.
echo Get it by installing "App Installer" from Microsoft Store, then run install.bat again.
exit /b 1

:refresh_path
rem Reload PATH from the registry: winget may have added a folder since this window opened.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%P;%LOCALAPPDATA%\Microsoft\WinGet\Links;%ProgramFiles%\WinGet\Links"
exit /b 0
