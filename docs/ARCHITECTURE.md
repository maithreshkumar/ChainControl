# Architecture

```text
Browser -> NGINX -> React / Django REST
                         |-- MySQL (workflow + projections)
                         |-- Redis (challenge TTL + nonce lock + Celery)
                         |-- MinIO (encrypted objects)
                         `-- Web3.py -> 4-validator Besu QBFT -> contracts
                                                        |
                                              events -> indexer -> MySQL
```

Blockchain writes pass through one transaction service. It reserves the pending EVM nonce under a Redis lock, records an idempotency key, signs, submits, and tracks the receipt. Application workflows never report completion before confirmation.

The contracts are `TrustAccessManager`, `IdentityRegistry`, and `AssetRegistry`. The access manager owns granular blockchain roles. The identity registry stores a DID hash, controller address, state, and key version. The asset registry stores a unique application UUID hash, content/metadata hashes, NFT ownership, and lifecycle state.

Partial failures are recovered by an event indexer and reconciliation jobs. Blockchain wins for ownership and security state; content-hash mismatches create alerts and are never silently rewritten.

