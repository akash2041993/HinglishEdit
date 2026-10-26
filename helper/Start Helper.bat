@echo off
title Hinglish Edit helper
cd /d "%~dp0"
echo Starting the Hinglish Edit helper...
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 run_helper.py
  goto done
)
where python >nul 2>nul
if %errorlevel%==0 (
  python run_helper.py
  goto done
)
echo.
echo Python 3 is not installed.
echo Install it from python.org (tick "Add python.exe to PATH"), then double-click this file again.
start "" https://www.python.org/downloads/windows/
:done
pause
