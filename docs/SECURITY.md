# Security Design

- Passwords use Django password hashing. JWT access tokens are short-lived.
- High-risk actions require a one-time DID challenge bound to identity, purpose, and session context.
- Challenge values use `secrets.token_urlsafe`, expire in Redis/database, and are atomically consumed before authorization.
- Ethereum signatures are verified against the identity controller; an otherwise valid signature is rejected unless identity state is `ACTIVE`.
- Asset bytes are hashed with SHA-256 and encrypted with a fresh 256-bit data key using AES-GCM. The data key is wrapped with the environment master key.
- Private keys, raw data keys, passwords, personal details, and files never go on-chain or into logs.
- Backend permissions are codename based and scoped by department/classification. Smart contracts independently enforce blockchain roles.
- Sensitive operations fail closed when Besu, Redis, or required storage is unavailable.
- Observer endpoints require `observer.view`, expose no mutation methods, and never return private keys, wallet material, wrapped keys, master keys, plaintext files, access codes, or MinIO credentials.
- Administrative recovery requires a named active administrator, reason, Asset UUID, and explicit output. AES-GCM authentication and the registered SHA-256 must pass. Success and failure create `ADMIN_DECRYPT` events without key material.

The development environment uses an environment-provided signer and master key. In the demo, storage administration and decryption authority may be controlled by the same operator. Production must separate them and migrate signing/key wrapping to HSM/KMS-backed services. MinIO credentials authorize object storage; they do not themselves decrypt asset data.

## Besu membership security

New nodes require an expiring single-use enrollment code, strict enode/public-key/address verification, unique identity, a scoped hashed node credential, and explicit Django superuser approval. Approval/revocation must be confirmed by the actual Besu `PERM` API before state changes are accepted. Validator authority additionally requires real QBFT voting.

Remote RPC is loopback-only; only P2P is bound to the selected private-overlay address. Node private keys never enter Django, package archives, logs, or another computer. `PERM`, `ADMIN`, and `QBFT` management APIs must stay on Docker/private networks. See `NETWORK_SECURITY.md` for the threat boundaries and response guidance.
