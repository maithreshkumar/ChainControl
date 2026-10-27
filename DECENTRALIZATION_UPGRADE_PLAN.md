# ChainControl Decentralization Upgrade Plan

## Scope and safety invariant

This upgrade converts the existing same-host, four-validator Besu demonstration into a dynamically admitted permissioned network without rebuilding ChainControl or changing its business contracts. The existing MySQL, MinIO, Redis, identity, inventory, asset, transfer, wallet, and audit workflows remain intact.

The current chain is not disposable. No implementation step may delete or recreate `besu-config`, `besu-1-data`, `besu-2-data`, `besu-3-data`, or `besu-4-data`; run `docker compose down --volumes`; regenerate the canonical genesis; copy a validator private key; or redeploy the contracts as part of this upgrade.

The Docker engine was unavailable during the 25 September 2026 audit, so the live generated genesis could not be exported or hashed. Activation of a remote node is therefore gated on exporting the exact `/generated/genesis.json` from the existing `besu-config` volume after Docker is available. Implementation that does not mutate the live chain can proceed before that verification.

## 1. Current blockchain architecture

- Docker Compose runs MySQL, Redis, MinIO, Django/Gunicorn, Celery worker/beat, the business React app, a separate React Observer, NGINX, one Besu bootstrap job, and four Besu validator containers.
- All four validators run on one Docker engine and one `172.20.0.0/16` bridge network. This is a multi-process QBFT demonstration, not geographic decentralization.
- Validator 1 exposes HTTP JSON-RPC on host port `8545`; the other validator RPC endpoints are reachable only inside Compose.
- Django uses `WEB3_PROVIDER_URL`, presently defaulting to `http://besu-validator-1:8545`, for transactions and chain reads.
- Celery submits and tracks blockchain transactions; MySQL stores workflow state and blockchain projections; MinIO stores independently encrypted asset bytes.
- The Observer is separately built and served on port `5174`, but today all of its block, transaction, analytics, NFT, and network requests go through Django. It does not yet prove a local-node blockchain copy.

## 2. Existing node configuration

- Image: `hyperledger/besu:25.7.0`.
- Chain ID: `1337`.
- Consensus: QBFT, 10-second minimum block period, 60-second experimental empty-block period for newly initialized chains, epoch length 30000, request timeout 20 seconds.
- Sync mode: `FULL`.
- P2P port: `30303` on every container.
- HTTP RPC: `8545`, bound to `0.0.0.0` inside each container with `ETH,NET,QBFT,WEB3` enabled.
- RPC host allowlist and CORS are currently `*`; this is acceptable only inside the isolated development bridge and must not be copied into a remote/public deployment.
- The bootstrap job generates node keys and genesis into the named `besu-config` volume. Each validator has an independent persistent chain-data volume.
- `static-nodes.json` is generated with four hardcoded Docker IP enodes. There is no Besu node permissioning allowlist today.

## 3. Existing validator configuration

- `infrastructure/besu/qbftConfigFile.json` generates exactly four initial validators.
- `infrastructure/besu/bootstrap.sh` assumes node numbers 1–4 and fixed addresses `172.20.0.11` through `.14`.
- `docker-compose.yml` defines four explicit validator services and volumes.
- `BlockchainHealthView` defaults to four explicit RPC URLs and reports consensus healthy only when every result contains exactly four validators.
- Initial validators in genesis are legitimate bootstrap validators. Future membership must be changed through real QBFT votes; the genesis list will not be treated as the permanent validator set.

## 4. Current limitations

- Fixed node and validator count in genesis generation, bootstrap scripting, Compose, backend health logic, documentation, and Observer labels.
- No admission token, enrollment request, node registry, heartbeat, revocation, or version tracking.
- No actual Besu node permissioning; possession of network reachability and genesis/static peers is currently sufficient to attempt peering.
- No governed validator promotion/removal service using `qbft_proposeValidatorVote` and validator-set verification.
- No remote-node package and no Windows-first setup/start/status scripts.
- No secure distribution of the exact existing genesis and approved bootstrap peers.
- Observer reads central Django rather than local Besu and cannot show local sync progress independently of Django.
- Same-host Docker IPs cannot support NAT-separated computers.

## 5. Target architecture

The target has two deliberately separate control planes:

1. **Existing blockchain data plane** — independently keyed Besu full nodes and a governed subset of QBFT validators communicate over a private overlay network. Once admitted, they continue peering, syncing, and reaching consensus when Django or Observer is unavailable.
2. **Django admission/metadata plane** — Django issues expiring single-use enrollment codes, reviews node requests, publishes signed/hashed network configuration, records health projections, orchestrates allowlist propagation, and initiates QBFT governance. It is not in the block-production path.

Every remote package runs its own Besu data volume and local Observer. The Observer reads blockchain data from local Besu. Django enrichment is optional and degrades independently.

## 6. Files and modules that must change

- New Django app `backend/apps/network/` containing models, migrations, serializers, enrollment authentication/throttling, views/URLs, admin, admission service, Besu RPC permissioning client, peer/bootstrap configuration service, validator-governance service, health service, periodic tasks, and tests.
- `backend/config/settings.py`, `urls.py`, and Celery schedule for network-specific configuration and health checks.
- `backend/apps/blockchain/views.py` and Observer network types/UI to remove fixed-four health assumptions and discover the actual validator set.
- `infrastructure/besu/bootstrap.sh`, `start-node.sh`, and Compose environment/mounts to enable file-based node permissioning and internal `PERM`/`QBFT` management APIs safely.
- A reusable `node-package/` with Docker Compose, exact-genesis placeholder/export workflow, local permissions config, Observer, setup/start/stop/status scripts, heartbeat/config agent, `.env.example`, and README.
- Observer data access so chain reads use local JSON-RPC while optional Django metadata is isolated.
- Required network and security documentation plus updates to existing architecture/deployment/status documents.

## 7. Files and modules that must not change

- Solidity contracts and `blockchain/deployments/1337.json`, unless a demonstrated compatibility defect requires a separately approved migration.
- Identity, asset, inventory, transfer, wallet-provisioning, MinIO encryption/storage, and normal business frontend flows.
- Existing MySQL engine/database choice and existing business migrations.
- Existing validator private keys, chain data, contract addresses, transaction history, and asset/NFT state.
- MinIO topology; object replication is outside this upgrade.

## 8. Networking strategy

- Prototype remote connectivity uses a private WireGuard-compatible overlay (for example Tailscale or an organization-managed WireGuard network). Overlay installation/login is a documented one-time prerequisite, not silently automated.
- Besu P2P listens on the overlay-reachable address/port. Public internet exposure of RPC, WebSocket, `PERM`, `ADMIN`, or Django admin is prohibited.
- Local Observer reaches local Besu through a same-host NGINX `/rpc/` proxy or Docker-private service name. Besu RPC is published only on `127.0.0.1` when host access is required.
- Central admission/metadata endpoints use HTTPS or the same private overlay. Production TLS termination is mandatory.
- Multiple approved bootstrap peers are returned dynamically. A single permanent peer is not assumed.
- NAT reachability and overlay address are validated before marking a node ONLINE.

## 9. Node enrollment flow

1. A Django superuser creates an expiring, single-use enrollment token associated with an intended owner (optional) and FULL_NODE request.
2. `setup.bat` creates a UUID and independent Besu node key locally, derives only the public key/address/enode, and stores the private key in the local Docker volume.
3. The setup agent submits the token, UUID, name, public identity, enode, overlay address, ports, and software version. No private key is transmitted.
4. Django applies throttles, validates the token/enode/UUID, rejects duplicates and revoked identities, consumes the token, and records a PENDING node plus audit event.
5. The node polls a narrowly scoped status endpoint using a random enrollment receipt credential.
6. A Django superuser approves or rejects in the dedicated Network Administration area.
7. Approval propagates the enode to every reachable active member’s Besu node allowlist, verifies the result, and only then publishes canonical genesis hash/config plus multiple permitted bootstrap peers and a per-node heartbeat credential.
8. The node verifies chain ID and genesis hash, starts Besu, pulls the approved allowlist, connects, and reports real sync/peer/head data.

## 10. Validator-promotion flow

- Approval always creates a FULL_NODE first.
- Promotion is available only to a superuser and only for an APPROVED/ONLINE/FULL_NODE that is fully synchronized and has a valid Ethereum node address.
- The validator manager reads the actual validator set from Besu, submits `qbft_proposeValidatorVote(candidate, true)` to distinct current validator RPC endpoints, records each result, polls the real validator set, and marks the operation complete only after the candidate appears on-chain.
- The required vote count is derived from the active validator set and Besu results, never hardcoded.
- Removal submits `qbft_proposeValidatorVote(candidate, false)` and only changes the MySQL projection after the address disappears from the actual set.
- Failed/partial proposals remain visible and retryable; they never claim completion.

## 11. Observer deployment model

- Each node package runs Observer separately from Besu so either can restart independently.
- Blocks, receipts, transactions, peer count, sync state, current validators, and local head come directly from the local Besu JSON-RPC proxy.
- The node header shows UUID, configured name, role projection, enrollment/health status, local head, network head, peer count, enode, and measured sync percentage.
- ABI decoding uses the existing deployment ABI bundle for chain 1337. Optional friendly names/DIDs/assets come from central Django metadata endpoints.
- If Django is unavailable, raw blockchain viewing and ABI decoding continue; metadata panels show an explicit unavailable state.

## 12. Security model

- Enrollment tokens and node API credentials are generated with cryptographic randomness and stored only as salted hashes. Tokens expire and are single-use.
- Enrollment and polling endpoints use DRF scoped throttles; duplicate UUID, public key, node address, and normalized enode constraints fail closed.
- Heartbeats authenticate with a per-node bearer credential; a node can update only its own safe operational fields.
- Superuser checks are explicit and independent of Platform Admin/RBAC roles. Django Admin mutations retain CSRF protection.
- Enodes and overlay addresses are strictly parsed; RPC URLs are constructed from validated private/overlay addresses rather than accepted as arbitrary server-side URLs, preventing SSRF.
- Node private keys, wallet keys, enrollment plaintext tokens, API credentials, and MinIO secrets are never returned in lists/logs/audits.
- Permissioning changes are applied to all reachable active nodes and verified with `perm_getNodesAllowlist`; partial propagation is DEGRADED and blocks final approval.
- Runtime permissioning APIs remain private to Docker/overlay networks. Host RPC binds to loopback only.
- Network actions create `NODE_*` and `VALIDATOR_*` audit records with actor, node, result, reason, and correlation ID.

## 13. Failure handling

- Django outage: admitted nodes keep their last valid permission file, static/bootstrap peers, data, and validator set; consensus/sync continues. New enrollment and metadata enrichment pause.
- Observer outage: Besu continues; Observer reconnects to local RPC after restart.
- Full-node outage: last heartbeat ages to OFFLINE; restart reuses its data/key and Besu catches up automatically.
- Validator outage: health reflects the actual online validator/quorum condition; no fake healthy state is emitted.
- Partial allowlist propagation: approval remains APPROVED_PENDING_PROPAGATION/DEGRADED (represented by status plus configuration error) until all required reachable nodes confirm. Revocation follows the same fail-visible behavior.
- Central metadata failure: Observer retains raw chain functions and labels enrichment unavailable.
- Invalid genesis/chain ID: the node refuses to start against the target network and preserves its local data for diagnosis.

## 14. Migration path from the current node

1. Stop making topology changes; do not stop/delete the existing validator volumes.
2. When Docker is available, export the exact current `/generated/genesis.json`, compute SHA-256, record chain ID/head/validator set, and back up the five Besu named volumes before permissioning changes.
3. Register the four current validators in `BlockchainNode` using their existing public enodes/addresses and current internal management RPC endpoints. Never import their private keys into Django.
4. Generate a permission allowlist containing the four current enodes and place the same persisted config in each validator data path.
5. Restart one validator at a time with node permissioning and `PERM` enabled only on the private Docker interface; verify height, peers, and validator set after each restart.
6. Replace fixed-four health logic with registry discovery and actual QBFT membership checks.
7. Export the exact canonical genesis and approved bootstrap list into the node-package release artifact; never rerun genesis generation for a remote node.
8. Enroll a new FULL_NODE, verify independent synchronization and local Observer, then test governance promotion separately.

Rollback is one-validator-at-a-time removal of the permissioning flags while retaining data volumes and the unchanged genesis. No database or chain reset is part of rollback.

## 15. Testing strategy

- Model/serializer tests: state transitions, uniqueness, token expiry/single use, secret hashing, superuser boundaries, enode/address validation, revoked-node denial.
- Service tests: allowlist propagation/verification, partial failure, bootstrap response filtering, heartbeat authentication, offline detection, actual-validator discovery, promotion/removal vote orchestration, audit events.
- API tests: enrollment throttling, status credential isolation, heartbeat ownership, anonymous denial, superuser-only mutations.
- Besu integration tests: permissioned fifth node joins using the exact genesis, rejected node cannot peer, revoked node is removed, node reconnect/catch-up, QBFT promotion/removal changes the actual validator set.
- Observer tests: direct local-RPC blocks/transactions, real sync calculation, no fixed node rows, metadata-offline graceful degradation.
- Regression: full backend suite, both React builds/tests, Hardhat suite, migration check, Docker smoke tests, existing business workflows.
- Remote acceptance: execute the required Node 2–5 enrollment scenarios on independent data volumes; at least one test should use a physically separate overlay-connected Windows host before claiming geographic decentralization.

## 16. Definition of Done

- No application logic assumes exactly four total nodes or validators.
- Exact existing chain identity/history/contracts are preserved and verified by genesis hash, chain ID, contract addresses, and known block height.
- Independently keyed FULL_NODE enrollment, approval/rejection, permission propagation, bootstrap, synchronization, heartbeat, offline/reconnect, and revocation work end-to-end.
- A remote/local Observer reads that node’s own Besu and remains useful when Django metadata is down.
- Django superuser sees dynamic network totals, health, node table, pending requests, and non-fabricated topology data.
- Promotion/removal uses real QBFT proposals and verifies the actual validator set before updating projections.
- RPC/admin APIs are not publicly exposed; secrets/private keys are absent from Django and logs.
- Existing ChainControl business functionality and MySQL/MinIO design continue unchanged.
- Automated and live acceptance tests pass and documentation describes only behavior actually demonstrated.

## Visible implementation checklist

- [x] Inventory repository, fixed-node assumptions, ports, contracts, Observer path, and security conventions.
- [x] Record chain ID and deployed contract anchors (TrustAccessManager block 7494, IdentityRegistry 7495, AssetRegistry 7496).
- [x] Export/hash the exact live generated genesis and current validator/enode set (`f7c74cf20c85e0281ae1bf7508c761dccace45ac88526b0483e1370bc789b106`, chain 1337).
- [x] Add the network-domain models, migrations, validation, secrets, auditing, and superuser admin.
- [x] Add enrollment/status/heartbeat/config APIs with throttling and scoped credentials.
- [x] Add admission, permission propagation, bootstrap, health, and offline-detection services.
- [x] Enable Besu node permissioning without replacing genesis or data volumes; all four preserved validators live-confirm the same enforced allowlist.
- [x] Replace fixed-four health and validator assumptions with runtime discovery.
- [x] Add real QBFT validator promotion/removal orchestration.
- [x] Create the Windows-first reusable remote-node package with independent key generation.
- [x] Change node-package Observer to local Besu reads with optional Django-independent raw chain viewing.
- [x] Add dynamic network administration dashboard/topology data from real registry/peer snapshots.
- [ ] Complete physically separate remote-host enrollment/sync/reconnect/revocation and live validator add/remove acceptance; same-host live permissioning/health/Observer checks and all automated tests pass.
- [x] Update all required network and existing project documentation.
