# Node Enrollment

Enrollment admits an independently keyed Besu node; it does not make that node a validator.

## Administrator

1. Open `/admin/network/` as a Django superuser. Platform roles do not grant access.
2. Open **Enrollment tokens**, create a token, choose the intended owner if applicable, and set an expiry. The plaintext `JOIN-...` code is shown once; deliver it privately.
3. The remote operator runs `scripts\setup.bat` from the generated node package. The private node key remains in that computer's named Docker volume. Django receives only UUID, enode, public key/address, overlay address, ports, version, and the one-time code.
4. Review the PENDING node under **Blockchain nodes**. Confirm its owner, overlay address, node name, enode, and public identity.
5. Select **Approve selected pending nodes and propagate Besu permissioning** or reject it. Approval fails closed unless the exact existing genesis is registered and each managed Besu RPC confirms the allowlist change.
6. The remote setup process receives the exact genesis text/hash and approved bootnodes only after approval. It starts as `FULL_NODE`.

API routes are under `/api/v1/network/`: `POST enrollment/`, scoped `GET enrollment/status/<uuid>/`, `GET nodes/<uuid>/configuration/`, and `POST nodes/<uuid>/heartbeat/`.

Enrollment codes and node credentials are salted hashes in MySQL. A used, expired, malformed, duplicate, rejected, or revoked identity cannot silently re-enter. Never request, store, log, or transmit a node private key.

Before the first approval, run `python manage.py capture_network_genesis` inside the backend only after the existing chain is available. The command registers the mounted live genesis once and refuses replacement by a different hash.

