@echo off
REM Double-click this file to start the shop and open it in the browser.
REM The first time builds the app and can take several minutes.
REM Later starts are quick. Your bills and stock are kept between starts.

cd /d "%~dp0\.."

where docker >nul 2>&1
if errorlevel 1 goto no_docker

docker info >nul 2>&1
if errorlevel 1 goto docker_stopped

echo Starting MM Electricals. The first run downloads and builds the app.
echo Leave this window open until the browser opens.
echo.
docker compose up -d --build
if errorlevel 1 goto failed

echo.
echo Waiting for the shop to finish starting...
set /a TRIES=0

:wait
set /a TRIES+=1
curl.exe -fsS http://127.0.0.1:8000/api/v1/health/ >nul 2>&1
if not errorlevel 1 goto open
if %TRIES% GEQ 90 goto timeout
ping -n 3 127.0.0.1 >nul
goto wait

:open
start "" http://127.0.0.1:8000/
echo.
echo The shop is open in your browser.
echo To stop it later, double-click scripts\stopShop.bat
echo Closing this window does not stop the shop.
echo.
pause
exit /b 0

:no_docker
echo Docker Desktop is not installed.
echo Install it from https://www.docker.com/products/docker-desktop/ then run this file again.
echo.
pause
exit /b 1

:docker_stopped
echo Docker Desktop is not running.
echo Open Docker Desktop, wait until it says Running, then run this file again.
echo.
pause
exit /b 1

:failed
echo.
echo The shop did not start. The messages above are the reason.
echo.
pause
exit /b 1

:timeout
echo.
echo The shop took too long to start. Last log lines:
docker compose logs --tail 40
echo.
pause
exit /b 1
