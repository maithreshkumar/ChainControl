# ChainControl Node

This package creates one independent Hyperledger Besu full node and a local Blockchain Observer. It never contains an existing validator key and it never copies blockchain database files from another computer.

## Before setup

1. Install and start Docker Desktop.
2. Join the private overlay network selected by the ChainControl administrator (for example, the organization Tailscale/WireGuard network).
3. Ask the Django superuser for one expiring enrollment code and the private/HTTPS ChainControl URL.
4. Ensure inbound TCP and UDP `30303` are permitted on the private overlay interface only.

## Install

1. Extract the package to a normal writable folder.
2. Run `scripts\setup.bat`. A Windows setup form opens.
3. Enter the ChainControl URL, node name, overlay IPv4 address, and paste the enrollment code into the on-screen text box. The form supports normal Ctrl+V and right-click paste.
4. Leave the window open while the superuser reviews the PENDING request. You may close it safely and run `setup.bat` again later.
5. After approval, run `scripts\start.bat`.
6. Open `http://localhost:5174`.

The node key is generated inside the `chaincontrol-<node UUID>-data` Docker volume. Only its public identity is enrolled. `.node\credential` is a scoped control-plane secret; do not share it.

`scripts\setup-cli.bat` remains available as a fallback for machines where Windows Forms is unavailable.

## Daily commands

- `scripts\start.bat` — start Besu, agent, and Observer.
- `scripts\status.bat` — show containers and real Besu synchronization state.
- `scripts\stop.bat` — stop services without deleting key or chain data.
- `scripts\reset-dev-node.bat` — destructive development-only reset requiring an exact confirmation phrase.

After downtime, start the node normally. Besu resumes from its persistent data volume and automatically requests missing blocks from approved peers.

## Troubleshooting

- **Pending approval:** the administrator must approve the request in `/admin/network/`; setup can be rerun without generating a new identity.
- **Rejected/revoked:** ask the administrator for the recorded reason. Do not delete or reuse the identity to bypass policy.
- **No peers:** confirm the overlay is connected, this node's overlay IP has not changed, and TCP/UDP `30303` is reachable between approved peers.
- **Sync appears stuck:** run `status.bat`, then `docker compose logs --tail=200 besu-validator-1`. A peer count of zero is a connectivity/permissioning issue.
- **Observer unavailable:** check `docker compose ps observer`. Besu keeps running if Observer is stopped.
- **Django unavailable:** Besu and raw local Observer chain data continue. Enrollment, heartbeat, configuration revisions, and friendly metadata wait for Django to return.
- **Wrong genesis error:** stop. Do not replace the local file or volume. Ask the administrator to verify the canonical SHA-256 and chain ID.

Never expose local RPC (`8545`), WebSocket, PERM, or ADMIN APIs to the public internet. This package binds RPC to `127.0.0.1`; P2P binds to the declared private overlay address.
