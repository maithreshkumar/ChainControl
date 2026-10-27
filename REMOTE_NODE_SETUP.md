# Join the ChainControl Blockchain from Another Windows Computer

This guide is for the person operating the **new computer**. The ChainControl administrator performs the approval and main-network configuration separately.

> Do not begin enrollment until the administrator confirms that the ChainControl private URL and a Tailscale-reachable blockchain bootnode are ready.

## What this package creates

The package creates:

- one independent Hyperledger Besu **full/replica node**;
- a local read-only Blockchain Observer webpage;
- an agent that reports node health to ChainControl;
- a unique node identity and persistent blockchain database on this computer.

It does not make this computer a validator. It does not contain an administrator, validator, or user wallet private key.

## Information to obtain from the administrator

Before starting, obtain all of the following:

1. `ChainControl-Node.zip` from the administrator.
2. An invitation to the administrator's Tailscale network.
3. The ChainControl private URL, for example `http://100.x.y.z`.
4. One unused, unexpired enrollment code beginning with `JOIN-`.

Every computer needs its own enrollment code. Never reuse another node's extracted folder, `.env`, `.node` directory, Docker volume, credential, or private key.

For the current ChainControl deployment, the administrator-supplied private URL is:

```text
http://100.114.144.74
```

## Step 1 — Install Docker Desktop

1. Open the official Docker installation page:
   <https://docs.docker.com/desktop/setup/install/windows-install/>
2. Download and install Docker Desktop for Windows.
3. Select the WSL 2 backend when the installer offers that option.
4. Restart Windows if requested.
5. Open Docker Desktop and wait until it reports that the engine is running.
6. Open PowerShell and verify:

   ```powershell
   docker version
   docker compose version
   ```

Both commands must complete successfully before continuing.

## Step 2 — Install and connect Tailscale

1. Open the official Tailscale Windows installation page:
   <https://tailscale.com/docs/install/windows>
2. Download and install Tailscale.
3. Sign in using the account or invitation authorized by the ChainControl administrator.
4. Confirm in the Tailscale application that this computer and the main ChainControl computer are connected.
5. Copy this computer's Tailscale IPv4 address. It normally begins with `100.`. You can also obtain it in PowerShell:

   ```powershell
   tailscale ip -4
   ```

6. Test the private connection using the main computer's Tailscale IP supplied by the administrator:

   ```powershell
   tailscale ping 100.114.144.74
   Test-NetConnection 100.114.144.74 -Port 80
   ```

The TCP test must show `TcpTestSucceeded : True`.

## Step 3 — Allow the blockchain P2P port

Open PowerShell **as Administrator** and run:

```powershell
New-NetFirewallRule -DisplayName "ChainControl Besu P2P TCP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 30303 -RemoteAddress 100.64.0.0/10
New-NetFirewallRule -DisplayName "ChainControl Besu P2P UDP" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 30303 -RemoteAddress 100.64.0.0/10
```

These rules allow the Besu peer port only from Tailscale's private IPv4 range. Do not expose RPC ports `8545` or `8546` to the internet.

## Step 4 — Extract the node package

1. Right-click `ChainControl-Node.zip` and select **Extract All**.
2. Place the extracted `ChainControl-Node` folder in a normal writable location such as Documents or Desktop.
3. Do not run the package directly from inside the ZIP file.
4. Do not copy any `.env`, `.node`, `config`, or Docker volume data from another node.

## Step 5 — Submit enrollment

1. Open the extracted `ChainControl-Node` folder.
2. Double-click `scripts\setup.bat`.
3. Complete the setup form:

   | Field | Value |
   |---|---|
   | ChainControl private URL | `http://100.114.144.74` |
   | Node name | A unique descriptive name, such as `Finance-Laptop-Node` |
   | Private/overlay IPv4 | This computer's Tailscale IPv4 address |
   | Enrollment code | The unused `JOIN-...` code supplied by the administrator |
   | P2P port | `30303` |
   | RPC port | `8545` |
   | Observer port | `5174` |

4. Select **Submit enrollment**.
5. The request initially remains pending. Tell the administrator the node name shown in the form.
6. Leave the setup window open while the administrator approves it. If the window is closed, run `setup.bat` again after approval. Do not request a second code and do not delete the generated files.

## Step 6 — Start and verify the node

After the administrator confirms approval:

1. If setup was closed, run `scripts\setup.bat` again and wait for **Approval confirmed**.
2. Double-click `scripts\start.bat`.
3. Wait for the containers to start.
4. Double-click `scripts\status.bat`.
5. Open the local Observer:

   <http://localhost:5174>

The Observer address works only on this computer. The node may initially show **SYNCING** while it downloads existing blocks. Leave Docker Desktop and the computer running until it becomes **ONLINE**.

Healthy results are:

- all four Docker services are running;
- Besu reports at least one peer;
- block height increases and approaches the network height;
- ChainControl shows the node as `SYNCING` and then `ONLINE`.

## Daily use

From the extracted folder:

- `scripts\start.bat` — start the node safely;
- `scripts\status.bat` — view synchronization and container status;
- `scripts\stop.bat` — stop services without deleting the key or blockchain data.

The equivalent PowerShell command is:

```powershell
docker compose up -d
```

Use `docker compose up -d`, not `docker start`, so every required service is started consistently.

## Security rules

- Keep `.node\credential` private.
- Never copy or share the Docker volume named `chaincontrol-<node UUID>-data`.
- Never share the Besu private key stored in that volume.
- Do not publish RPC `8545`, WebSocket `8546`, PERM, or ADMIN APIs publicly.
- Do not edit or replace `config\genesis.json`.
- Do not use `reset-dev-node.bat` unless the administrator explicitly authorizes a complete local-node reset.

## Troubleshooting

### `setup.bat` cannot reach ChainControl

Run:

```powershell
tailscale ping 100.114.144.74
Test-NetConnection 100.114.144.74 -Port 80
```

If either fails, send the results to the administrator.

### Enrollment remains pending

The Django administrator has not approved it yet. Do not submit another enrollment.

### Observer says site cannot be reached

From the extracted `ChainControl-Node` folder, run:

```powershell
docker compose up -d
docker compose ps
```

Then reopen <http://localhost:5174>.

### Peer count stays at zero

Confirm that Tailscale is connected, the private IP in `.env` is still correct, and the TCP/UDP `30303` firewall rules exist. Send the following output to the administrator:

```powershell
scripts\status.bat
docker compose logs --tail=200 besu-validator-1
```

### Wrong-genesis or permissioning error

Stop the node with `scripts\stop.bat` and contact the administrator. Do not delete the Docker volume or replace the genesis file.

## Official downloads

- Docker Desktop for Windows: <https://docs.docker.com/desktop/setup/install/windows-install/>
- Tailscale for Windows: <https://tailscale.com/docs/install/windows>
- Tailscale connectivity and firewall reference: <https://tailscale.com/docs/reference/faq/firewall-ports>
