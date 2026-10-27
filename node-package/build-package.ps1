[CmdletBinding()]
param([string]$OutputDirectory)

$ErrorActionPreference = 'Stop'
$OutputDirectory = if ($OutputDirectory) { $OutputDirectory } else { Join-Path $PSScriptRoot 'dist/ChainControl-Node' }
$repo = Split-Path -Parent $PSScriptRoot
$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'dist'))
if (-not $resolvedOutput.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must be inside $allowedRoot"
}
if (Test-Path $resolvedOutput) { Remove-Item -LiteralPath $resolvedOutput -Recurse -Force }
New-Item -ItemType Directory -Force $resolvedOutput | Out-Null
Copy-Item "$PSScriptRoot\docker-compose.yml","$PSScriptRoot\.env.example","$PSScriptRoot\README.md" -Destination $resolvedOutput
Copy-Item "$PSScriptRoot\scripts","$PSScriptRoot\agent" -Destination $resolvedOutput -Recurse
New-Item -ItemType Directory -Force "$resolvedOutput\config" | Out-Null
Copy-Item "$repo\observer" -Destination "$resolvedOutput\observer" -Recurse
Remove-Item "$resolvedOutput\observer\node_modules","$resolvedOutput\observer\dist" -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $resolvedOutput -Directory -Recurse -Filter __pycache__ | Remove-Item -Recurse -Force
Get-ChildItem $resolvedOutput -File -Recurse -Filter *.tsbuildinfo | Remove-Item -Force
New-Item -ItemType Directory -Force "$resolvedOutput\observer\public\deployments" | Out-Null
Copy-Item "$repo\blockchain\deployments\1337.json" -Destination "$resolvedOutput\observer\public\deployments\1337.json"
Compress-Archive -Path "$resolvedOutput\*" -DestinationPath "$PSScriptRoot\dist\ChainControl-Node.zip" -Force
Write-Host "Created $resolvedOutput"
Write-Host "Created $PSScriptRoot\dist\ChainControl-Node.zip"
