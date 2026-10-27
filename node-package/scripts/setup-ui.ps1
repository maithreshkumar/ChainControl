[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

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

$envValues = Read-EnvFile (Join-Path $Root '.env')
if (-not $envValues.Count) { $envValues = Read-EnvFile (Join-Path $Root '.env.example') }

$defaults = @{
    CHAINCONTROL_API_URL = ''
    NODE_NAME = ''
    NODE_UUID = ''
    OVERLAY_IP = ''
    P2P_PORT = '30303'
    RPC_PORT = '8545'
    WS_PORT = '8546'
    OBSERVER_PORT = '5174'
    CHAIN_ID = '1337'
    NODE_VERSION = '1.0.0'
    BOOTNODES = ''
}
foreach ($key in $defaults.Keys) {
    if (-not $envValues.ContainsKey($key)) { $envValues[$key] = $defaults[$key] }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'ChainControl Node Setup'
$form.StartPosition = 'CenterScreen'
$form.ClientSize = New-Object System.Drawing.Size(610, 585)
$form.MinimumSize = New-Object System.Drawing.Size(626, 624)
$form.BackColor = [System.Drawing.Color]::FromArgb(7, 17, 31)
$form.ForeColor = [System.Drawing.Color]::FromArgb(230, 240, 248)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.AutoScaleMode = 'Dpi'

$title = New-Object System.Windows.Forms.Label
$title.Text = 'Connect a ChainControl node'
$title.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 18)
$title.ForeColor = [System.Drawing.Color]::FromArgb(67, 220, 198)
$title.Location = New-Object System.Drawing.Point(28, 22)
$title.AutoSize = $true
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = 'Enter the details supplied by the network administrator. Ctrl+V works in every field.'
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(150, 174, 193)
$subtitle.Location = New-Object System.Drawing.Point(31, 61)
$subtitle.Size = New-Object System.Drawing.Size(545, 42)
$form.Controls.Add($subtitle)

$fields = @(
    @{ Key='CHAINCONTROL_API_URL'; Label='ChainControl private URL'; Example='Example: http://192.168.1.20' },
    @{ Key='NODE_NAME'; Label='Node name'; Example='Example: Accounts-Full-Node' },
    @{ Key='OVERLAY_IP'; Label='This computer private / overlay IPv4'; Example='Example: 100.64.0.25' },
    @{ Key='ENROLLMENT_CODE'; Label='One-time enrollment code'; Example='Paste the JOIN-... code here' }
)

$controls = @{}
$top = 108
foreach ($field in $fields) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $field.Label
    $label.Location = New-Object System.Drawing.Point(32, $top)
    $label.AutoSize = $true
    $label.ForeColor = [System.Drawing.Color]::FromArgb(215, 227, 237)
    $form.Controls.Add($label)

    $box = New-Object System.Windows.Forms.TextBox
    $box.Location = New-Object System.Drawing.Point(32, ($top + 25))
    $box.Size = New-Object System.Drawing.Size(544, 30)
    $box.BorderStyle = 'FixedSingle'
    $box.BackColor = [System.Drawing.Color]::FromArgb(11, 27, 42)
    $box.ForeColor = [System.Drawing.Color]::FromArgb(231, 240, 246)
    $box.Text = if ($field.Key -eq 'ENROLLMENT_CODE') { '' } else { [string]$envValues[$field.Key] }
    $controls[$field.Key] = $box
    $form.Controls.Add($box)

    $hint = New-Object System.Windows.Forms.Label
    $hint.Text = $field.Example
    $hint.Location = New-Object System.Drawing.Point(34, ($top + 58))
    $hint.AutoSize = $true
    $hint.ForeColor = [System.Drawing.Color]::FromArgb(111, 135, 154)
    $hint.Font = New-Object System.Drawing.Font('Segoe UI', 8.5)
    $form.Controls.Add($hint)
    $top += 91
}

$portsLabel = New-Object System.Windows.Forms.Label
$portsLabel.Text = 'Ports (change these only when testing another node on the same computer)'
$portsLabel.Location = New-Object System.Drawing.Point(32, 471)
$portsLabel.AutoSize = $true
$portsLabel.ForeColor = [System.Drawing.Color]::FromArgb(150, 174, 193)
$form.Controls.Add($portsLabel)

$portFields = @(
    @{ Key='P2P_PORT'; X=32; Width=120; Prefix='P2P' },
    @{ Key='RPC_PORT'; X=168; Width=120; Prefix='RPC' },
    @{ Key='OBSERVER_PORT'; X=304; Width=136; Prefix='Observer' }
)
foreach ($field in $portFields) {
    $box = New-Object System.Windows.Forms.TextBox
    $box.Location = New-Object System.Drawing.Point($field.X, 500)
    $box.Size = New-Object System.Drawing.Size($field.Width, 28)
    $box.BorderStyle = 'FixedSingle'
    $box.BackColor = [System.Drawing.Color]::FromArgb(11, 27, 42)
    $box.ForeColor = [System.Drawing.Color]::FromArgb(231, 240, 246)
    $box.Text = [string]$envValues[$field.Key]
    $controls[$field.Key] = $box
    $form.Controls.Add($box)

    $prefix = New-Object System.Windows.Forms.Label
    $prefix.Text = $field.Prefix
    $prefix.Location = New-Object System.Drawing.Point(($field.X + 4), 531)
    $prefix.AutoSize = $true
    $prefix.ForeColor = [System.Drawing.Color]::FromArgb(111, 135, 154)
    $prefix.Font = New-Object System.Drawing.Font('Segoe UI', 8)
    $form.Controls.Add($prefix)
}

$connect = New-Object System.Windows.Forms.Button
$connect.Text = 'Submit enrollment'
$connect.Location = New-Object System.Drawing.Point(449, 495)
$connect.Size = New-Object System.Drawing.Size(127, 38)
$connect.FlatStyle = 'Flat'
$connect.FlatAppearance.BorderSize = 0
$connect.BackColor = [System.Drawing.Color]::FromArgb(67, 220, 198)
$connect.ForeColor = [System.Drawing.Color]::FromArgb(4, 19, 26)
$connect.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 9.5)
$connect.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.AcceptButton = $connect
$form.Controls.Add($connect)

$form.Add_FormClosing({
    param($sender, $eventArgs)
    if ($form.DialogResult -ne [System.Windows.Forms.DialogResult]::OK) { return }
    foreach ($required in 'CHAINCONTROL_API_URL','NODE_NAME','OVERLAY_IP','ENROLLMENT_CODE') {
        if ([string]::IsNullOrWhiteSpace($controls[$required].Text)) {
            [System.Windows.Forms.MessageBox]::Show("$required is required.", 'ChainControl Node Setup', 'OK', 'Warning') | Out-Null
            $eventArgs.Cancel = $true
            return
        }
    }
    foreach ($portKey in 'P2P_PORT','RPC_PORT','OBSERVER_PORT') {
        $port = 0
        if (-not [int]::TryParse($controls[$portKey].Text, [ref]$port) -or $port -lt 1 -or $port -gt 65535) {
            [System.Windows.Forms.MessageBox]::Show("$portKey must be a number from 1 to 65535.", 'ChainControl Node Setup', 'OK', 'Warning') | Out-Null
            $eventArgs.Cancel = $true
            return
        }
    }
})

$result = $form.ShowDialog()
if ($result -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }

$envValues.CHAINCONTROL_API_URL = $controls.CHAINCONTROL_API_URL.Text.Trim().TrimEnd('/')
$envValues.NODE_NAME = $controls.NODE_NAME.Text.Trim()
$envValues.OVERLAY_IP = $controls.OVERLAY_IP.Text.Trim()
$envValues.P2P_PORT = $controls.P2P_PORT.Text.Trim()
$envValues.RPC_PORT = $controls.RPC_PORT.Text.Trim()
$envValues.WS_PORT = if ($envValues.WS_PORT) { $envValues.WS_PORT } else { '8546' }
$envValues.OBSERVER_PORT = $controls.OBSERVER_PORT.Text.Trim()
$envValues.CHAIN_ID = if ($envValues.CHAIN_ID) { $envValues.CHAIN_ID } else { '1337' }
$envValues.NODE_VERSION = if ($envValues.NODE_VERSION) { $envValues.NODE_VERSION } else { '1.0.0' }
Write-EnvFile $envValues

$enrollmentCode = $controls.ENROLLMENT_CODE.Text.Trim()
$form.Dispose()
& (Join-Path $PSScriptRoot 'setup.ps1') -EnrollmentCode $enrollmentCode
exit $LASTEXITCODE
