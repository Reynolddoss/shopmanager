@echo off
REM Double-click this file to stop the shop.
REM The database, photos, and backups stay on this PC.

cd /d "%~dp0\.."

where docker >nul 2>&1
if errorlevel 1 goto no_docker

docker compose down
if errorlevel 1 goto failed

echo.
echo Shop stopped. Your bills and stock are kept.
echo Double-click scripts\startShop.bat to open it again.
echo.
pause
exit /b 0

:no_docker
echo Docker Desktop is not installed, so the shop is not running.
echo.
pause
exit /b 1

:failed
echo.
echo Could not stop the shop. The messages above are the reason.
echo.
pause
exit /b 1
