@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
echo WARNING: This permanently deletes ONLY this package's local Besu chain copy and node private key.
echo It does not affect the shared ChainControl network, but this identity must be re-enrolled.
set /p CONFIRM=Type DELETE-THIS-DEV-NODE to continue: 
if /I not "%CONFIRM%"=="DELETE-THIS-DEV-NODE" (
  echo Cancelled.
  exit /b 1
)
docker compose down --volumes
del /q .node\credential 2>nul
del /q config\node-address config\node-public-key config\genesis.json config\permissions_config.toml config\node-config.json 2>nul
echo Local development node data removed. Run setup.bat to create a new identity.
