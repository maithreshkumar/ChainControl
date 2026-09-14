# Threat Model

| Threat | Control |
|---|---|
| Stolen/replayed challenge | Short TTL, purpose binding, atomic one-time consume |
| Revoked key reused | Active identity checked after signature verification |
| Unauthorized mint/transfer | Django permission and independent contract role/owner checks |
| Concurrent signer nonce reuse | Redis lock and pending nonce reservation |
| Database owner tampering | Periodic on-chain reconciliation; critical alert |
| Object tampering | AES-GCM authentication plus SHA-256 comparison to on-chain proof |
| Duplicate jobs/events | Stable idempotency keys and `(tx_hash, log_index)` constraint |
| Compromised technical admin | No implicit business or blockchain authority |
| Validator/storage outage | Fail closed and preserve recoverable workflow state |
| Key disclosure in source/logs | Environment secrets, redaction, production HSM/KMS plan |

Residual risks include development signer custody, compromise of a QBFT supermajority, endpoint malware before encryption, and the physical/digital custody gap for physical assets.

