@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
docker compose ps
echo.
powershell.exe -NoLogo -NoProfile -Command "$body = '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"eth_syncing\",\"params\":[]}' ; try { Invoke-RestMethod -Method Post -Uri ('http://127.0.0.1:' + ((Get-Content .env | Where-Object { $_ -match '^RPC_PORT=' }) -replace '^RPC_PORT=','')) -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 6 } catch { Write-Host $_.Exception.Message; exit 1 }"

