@echo off
REM Double-click or run from cmd: builds NSIS Setup.exe on Windows.
cd /d "%~dp0\.."
set PYTHON=
if exist "%USERPROFILE%\.virtualenvs\shopmanager\Scripts\python.exe" set PYTHON=%USERPROFILE%\.virtualenvs\shopmanager\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PYTHON=%CD%\.venv\Scripts\python.exe
if "%PYTHON%"=="" set PYTHON=python
"%PYTHON%" scripts\buildSoftware.py %*
if errorlevel 1 pause
