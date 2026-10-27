[CmdletBinding()]
param(
    [string]$EnrollmentCode
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Read-EnvFile {
    param([string]$Path)
    $values = @{}
    if (Test-Path $Path) {
        foreach ($line in Get-Content $Path) {
            if ($line -match '^\s*([^#=]+)=(.*)$') { $values[$Matches[1].Trim()] = $Matches[2].Trim() }
        }
    }
    return $values
}

function Write-EnvFile {
    param([hashtable]$Values)
    $order = 'CHAINCONTROL_API_URL','NODE_NAME','NODE_UUID','OVERLAY_IP','P2P_PORT','RPC_PORT','WS_PORT','OBSERVER_PORT','CHAIN_ID','NODE_VERSION','BOOTNODES'
    $lines = foreach ($key in $order) { "$key=$($Values[$key])" }
    [IO.File]::WriteAllLines((Join-Path $Root '.env'), $lines, [Text.UTF8Encoding]::new($false))
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker Desktop is required and docker.exe is not on PATH.' }
docker version | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is installed but its Linux engine is not running.' }
docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 is not available.' }

$envValues = Read-EnvFile (Join-Path $Root '.env')
if (-not $envValues.CHAINCONTROL_API_URL) { $envValues.CHAINCONTROL_API_URL = Read-Host 'ChainControl URL (HTTPS or private-overlay URL)' }
if (-not $envValues.NODE_NAME) { $envValues.NODE_NAME = Read-Host 'Node name' }
if (-not $envValues.OVERLAY_IP) { $envValues.OVERLAY_IP = Read-Host 'This computer private overlay IPv4 address' }
if (-not $envValues.NODE_UUID) { $envValues.NODE_UUID = [guid]::NewGuid().ToString() }
foreach ($pair in @{'P2P_PORT'='30303';'RPC_PORT'='8545';'WS_PORT'='8546';'OBSERVER_PORT'='5174';'CHAIN_ID'='1337';'NODE_VERSION'='1.0.0';'BOOTNODES'=''}.GetEnumerator()) {
    if (-not $envValues[$pair.Key]) { $envValues[$pair.Key] = $pair.Value }
}
Write-EnvFile $envValues

New-Item -ItemType Directory -Force config,.node | Out-Null
if (-not (Test-Path 'config/node-public-key') -or -not (Test-Path 'config/node-address')) {
    Write-Host 'Generating an independent Besu identity in the local named volume...'
    docker compose --profile setup run --rm keygen
    if ($LASTEXITCODE -ne 0) { throw 'Besu could not generate the local node identity.' }
}
$publicKey = (Get-Content -Raw 'config/node-public-key').Trim() -replace '^0x',''
$nodeAddress = (Get-Content -Raw 'config/node-address').Trim()
if ($publicKey -notmatch '^[0-9a-fA-F]{128}$') { throw 'Besu returned an invalid public key.' }
if ($nodeAddress -notmatch '^0x[0-9a-fA-F]{40}$') { throw 'Besu returned an invalid node address.' }
$enode = "enode://$($publicKey.ToLower())@$($envValues.OVERLAY_IP):$($envValues.P2P_PORT)"

if (-not (Test-Path '.node/credential')) {
    $enrollmentCode = if ($EnrollmentCode) { $EnrollmentCode.Trim() } else { Read-Host 'One-time enrollment code' }
    if (-not $enrollmentCode) { throw 'A one-time enrollment code is required.' }
    $body = @{
        enrollment_code = $enrollmentCode
        node_uuid = $envValues.NODE_UUID
        node_name = $envValues.NODE_NAME
        enode = $enode
        node_public_key = $publicKey
        node_address = $nodeAddress
        host_or_overlay_address = $envValues.OVERLAY_IP
        p2p_port = [int]$envValues.P2P_PORT
        rpc_port = [int]$envValues.RPC_PORT
        ws_port = [int]$envValues.WS_PORT
        software_version = $envValues.NODE_VERSION
        requested_validator = $false
    } | ConvertTo-Json
    $response = Invoke-RestMethod -Method Post -Uri "$($envValues.CHAINCONTROL_API_URL.TrimEnd('/'))/api/v1/network/enrollment/" -ContentType 'application/json' -Body $body
    [IO.File]::WriteAllText((Join-Path $Root '.node/credential'), $response.node_credential, [Text.UTF8Encoding]::new($false))
    Write-Host "Enrollment submitted for $($response.node_uuid)."
}

$credential = (Get-Content -Raw '.node/credential').Trim()
$headers = @{ Authorization = "Node $credential" }
$baseUrl = $envValues.CHAINCONTROL_API_URL.TrimEnd('/')
Write-Host 'Waiting for Django superuser approval. Press Ctrl+C to stop; rerun setup.bat later.'
while ($true) {
    $status = Invoke-RestMethod -Headers $headers -Uri "$baseUrl/api/v1/network/enrollment/status/$($envValues.NODE_UUID)/"
    Write-Host "[$(Get-Date -Format T)] Status: $($status.status)"
    if ($status.status -eq 'REJECTED') { throw "Enrollment rejected: $($status.rejection_reason)" }
    if ($status.status -eq 'REVOKED') { throw "Node access revoked: $($status.revocation_reason)" }
    if ($status.configuration_ready) { break }
    Start-Sleep -Seconds 10
}

$configuration = Invoke-RestMethod -Headers $headers -Uri "$baseUrl/api/v1/network/nodes/$($envValues.NODE_UUID)/configuration/"
$genesisText = [string]$configuration.genesis_text
$genesisBytes = [Text.UTF8Encoding]::new($false).GetBytes($genesisText)
$sha256 = [Security.Cryptography.SHA256]::Create()
try { $sha = -join ($sha256.ComputeHash($genesisBytes) | ForEach-Object { $_.ToString('x2') }) } finally { $sha256.Dispose() }
if ($sha -ne $configuration.genesis_sha256.ToLower()) { throw 'Downloaded genesis failed SHA-256 validation.' }
if (Test-Path 'config/genesis.json') {
    $localSha = (Get-FileHash 'config/genesis.json' -Algorithm SHA256).Hash.ToLower()
    if ($localSha -ne $sha) { throw 'Existing local genesis belongs to a different network. No file was overwritten.' }
} else {
    [IO.File]::WriteAllBytes((Join-Path $Root 'config/genesis.json'), $genesisBytes)
}
$runtimeGenesis = $genesisText | ConvertFrom-Json
if ($null -ne $runtimeGenesis.config.transitions.qbft) {
    $runtimeTransitions = @()
    foreach ($transition in @($runtimeGenesis.config.transitions.qbft)) {
        $transition.PSObject.Properties.Remove('blockperiodseconds')
        $transition.PSObject.Properties.Remove('emptyblockperiodseconds')
        $transition.PSObject.Properties.Remove('xemptyblockperiodseconds')
        if (@($transition.PSObject.Properties.Name | Where-Object { $_ -ne 'block' }).Count -gt 0) {
            $runtimeTransitions += $transition
        }
    }
    if ($runtimeTransitions.Count -gt 0) {
        $runtimeGenesis.config.transitions.qbft = $runtimeTransitions
    } else {
        $runtimeGenesis.config.transitions.PSObject.Properties.Remove('qbft')
    }
    if (@($runtimeGenesis.config.transitions.PSObject.Properties).Count -eq 0) {
        $runtimeGenesis.config.PSObject.Properties.Remove('transitions')
    }
}
$runtimeGenesisText = ($runtimeGenesis | ConvertTo-Json -Depth 100) + "`n"
[IO.File]::WriteAllText((Join-Path $Root 'config/genesis-runtime.json'), $runtimeGenesisText, [Text.UTF8Encoding]::new($false))
$tomlLines = @('nodes-allowlist=[') + @($configuration.nodes_allowlist | ForEach-Object { '  ' + ($_ | ConvertTo-Json -Compress) + ',' }) + @(']','accounts-allowlist=[]')
[IO.File]::WriteAllLines((Join-Path $Root 'config/permissions_config.toml'), $tomlLines, [Text.UTF8Encoding]::new($false))
$envValues.CHAIN_ID = [string]$configuration.chain_id
$envValues.BOOTNODES = ($configuration.bootnodes -join ',')
Write-EnvFile $envValues
$nodeDocument = @{
    node_name=$envValues.NODE_NAME; node_uuid=$envValues.NODE_UUID; role='FULL_NODE'; status='APPROVED';
    local_block=0; network_block=0; sync_percentage=0; peer_count=0; enode=$enode;
    validator_count=0; network_name=$configuration.network_name
} | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $Root 'config/node-config.json'), $nodeDocument, [Text.UTF8Encoding]::new($false))

Write-Host 'Approval confirmed and canonical network configuration verified.'
Write-Host 'Run scripts\start.bat to start Besu, the control agent, and the local Observer.'
