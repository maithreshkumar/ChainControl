# Network Permissioning

ChainControl uses Besu local node permissioning. The canonical allowlist is persisted as `permissions_config.toml`; running managed nodes also receive and verify `perm_addNodesToAllowlist` or `perm_removeNodesFromAllowlist`. `PERM` is enabled only on Docker/private RPC, never a public interface.

Approval order is deliberate:

1. Validate PENDING identity and canonical genesis registration.
2. Add the exact normalized enode at every configured managed RPC endpoint.
3. Read `perm_getNodesAllowlist` at each endpoint and require confirmation.
4. Atomically persist the complete allowlist and increment its revision.
5. Mark the Django node APPROVED and release genesis/bootnodes.

If propagation fails, approval remains incomplete and records a failed audit plus configuration error. Revocation similarly removes and verifies the enode before recording REVOKED. Existing remote agents poll configuration revisions, atomically rewrite their local allowlist, call `perm_reloadPermissionsFromFile`, and add new approved peers.

Current validators copy the persisted configuration from the shared `besu-config` volume at restart, so runtime and restart state converge. Django can be unavailable after this: Besu keeps the last valid local file and the existing network continues.

Permissioning controls peering, not validator authority. Validator membership is a separate QBFT process described in `VALIDATOR_GOVERNANCE.md`.

