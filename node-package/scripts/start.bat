@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
docker compose up -d --build besu-validator-1 agent observer
if errorlevel 1 exit /b %ERRORLEVEL%
set "OBSERVER_PORT=5174"
for /f "tokens=1,* delims==" %%A in (.env) do if /I "%%A"=="OBSERVER_PORT" set "OBSERVER_PORT=%%B"
echo.
echo ChainControl node started. Observer: http://localhost:%OBSERVER_PORT%
docker compose ps
