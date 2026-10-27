# Architecture

```text
Browser -> NGINX -> Business React / Django REST
Browser :5174 -> Observer React -> read-only observer APIs
                         |-- MySQL (workflow + projections)
                         |-- Redis (challenge TTL + nonce lock + Celery)
                         |-- MinIO (encrypted objects)
                         `-- Web3.py -> dynamic Besu QBFT network -> contracts
                                                        |
                                              events -> indexer -> MySQL
```

Blockchain writes pass through one transaction service. It reserves the pending EVM nonce under a Redis lock, records an idempotency key, signs, submits, and tracks the receipt. Application workflows never report completion before confirmation.

The contracts are `TrustAccessManager`, `IdentityRegistry`, and `AssetRegistry`. The access manager owns granular blockchain roles. The identity registry stores a DID hash, controller address, state, and key version. The asset registry stores a unique application UUID hash, content/metadata hashes, NFT ownership, and lifecycle state.

Inventory is a separate relational bounded context: categories and dynamic variants define the catalogue; location stock holds quantity projections; append-only movements preserve the ledger; requests drive reserve/issue/return transitions under row locks. `STOCK_ITEM` and quantity-based `SOFTWARE_LICENSE` remain off-chain inventory. Individually governed physical/digital assets use the asset registry and may be NFT-backed.

The Observer shares authentication and read models but is separately built and served. Its backend reads Besu for blocks, receipts, validator membership, and transaction/event decoding, then enriches those records with business projections. No Observer endpoint accepts a mutation method.

Partial failures are recovered by an event indexer and reconciliation jobs. Blockchain wins for ownership and security state; content-hash mismatches create alerts and are never silently rewritten.

## Dynamic Besu network

The initial four Compose validators preserve the existing chain and contract state. Django's `apps.network` is a control plane for token-protected enrollment, superuser approval, Besu allowlist propagation, heartbeat projection, revocation, and QBFT governance. It is not in the block-production path.

Approved remote computers run an independently keyed full Besu node, persistent chain volume, node agent, and loopback-only Observer. Besu synchronizes blocks peer-to-peer over a private overlay. The local Observer reads local RPC; optional Django metadata can fail without hiding blockchain data. A full node becomes a validator only after real QBFT majority voting and actual validator-set verification.

See the root `DECENTRALIZATION_UPGRADE_PLAN.md` and the network-specific runbooks for the detailed boundaries.
