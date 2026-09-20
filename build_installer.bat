@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title PTS ECU BlackRed v10 - Build Installer

set "LOG=%CD%\build_log.txt"
>"%LOG%" echo PTS ECU BlackRed v10 build log
>>"%LOG%" echo Started: %DATE% %TIME%

echo ============================================================
echo   PTS ECU BlackRed v10 - ONE FILE INSTALLER BUILDER
echo ============================================================
echo.

rem Find a usable Python (3.10+ recommended; 3.12 preferred).
set "PY="
where py >nul 2>nul && (py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12")
if not defined PY where py >nul 2>nul && (py -3 -c "import sys" >nul 2>nul && set "PY=py -3")
if not defined PY where python >nul 2>nul && (python -c "import sys" >nul 2>nul && set "PY=python")
if not defined PY goto :NO_PYTHON

echo [1/5] Python: %PY%
%PY% -c "import sys; print(sys.version)" >>"%LOG%" 2>&1

if not exist ".buildvenv\Scripts\python.exe" (
  echo [2/5] Creating clean build environment...
  %PY% -m venv .buildvenv >>"%LOG%" 2>&1 || goto :FAIL
) else (
  echo [2/5] Reusing build environment...
)
set "VPY=%CD%\.buildvenv\Scripts\python.exe"

echo [3/5] Installing build requirements...
"%VPY%" -m pip install --upgrade pip >>"%LOG%" 2>&1 || goto :FAIL
"%VPY%" -m pip install -r requirements.txt >>"%LOG%" 2>&1 || goto :FAIL

echo [4/5] Building application EXE...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%VPY%" -m PyInstaller --clean --noconfirm PTS_ECU_BlackRed.spec >>"%LOG%" 2>&1 || goto :FAIL
if not exist "dist\PTS_ECU_BlackRed_v10.exe" goto :NO_APP_EXE

echo [5/5] Building single installer EXE...
set "NSIS="
if exist "%ProgramFiles(x86)%\NSIS\makensis.exe" set "NSIS=%ProgramFiles(x86)%\NSIS\makensis.exe"
if not defined NSIS if exist "%ProgramFiles%\NSIS\makensis.exe" set "NSIS=%ProgramFiles%\NSIS\makensis.exe"
if not defined NSIS if exist "%LOCALAPPDATA%\Programs\NSIS\makensis.exe" set "NSIS=%LOCALAPPDATA%\Programs\NSIS\makensis.exe"
if not defined NSIS goto :NO_NSIS

if exist "PTS_ECU_BlackRed_v10_Setup.exe" del /q "PTS_ECU_BlackRed_v10_Setup.exe"
"%NSIS%" installer.nsi >>"%LOG%" 2>&1 || goto :FAIL
if not exist "PTS_ECU_BlackRed_v10_Setup.exe" goto :FAIL

echo.
echo ============================================================
echo SUCCESS
echo Installer created:
echo %CD%\PTS_ECU_BlackRed_v10_Setup.exe
echo ============================================================
explorer /select,"%CD%\PTS_ECU_BlackRed_v10_Setup.exe"
pause
exit /b 0

:NO_PYTHON
echo ERROR: Python was not found.
echo Install Python 3.12 x64 and enable Python Launcher / PATH.
goto :SHOW_FAIL

:NO_NSIS
echo ERROR: NSIS makensis.exe was not found.
echo Expected for example: C:\Program Files (x86)\NSIS\makensis.exe
goto :SHOW_FAIL

:NO_APP_EXE
echo ERROR: PyInstaller finished without dist\PTS_ECU_BlackRed_v10.exe
goto :SHOW_FAIL

:FAIL
echo ERROR: Build command failed.

:SHOW_FAIL
echo.
echo Build did not complete. Open this log and send it if needed:
echo %LOG%
echo.
pause
exit /b 1
