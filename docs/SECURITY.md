# Security Design

- Passwords use Django password hashing. JWT access tokens are short-lived.
- High-risk actions require a one-time DID challenge bound to identity, purpose, and session context.
- Challenge values use `secrets.token_urlsafe`, expire in Redis/database, and are atomically consumed before authorization.
- Ethereum signatures are verified against the identity controller; an otherwise valid signature is rejected unless identity state is `ACTIVE`.
- Asset bytes are hashed with SHA-256 and encrypted with a fresh 256-bit data key using AES-GCM. The data key is wrapped with the environment master key.
- Private keys, raw data keys, passwords, personal details, and files never go on-chain or into logs.
- Backend permissions are codename based and scoped by department/classification. Smart contracts independently enforce blockchain roles.
- Sensitive operations fail closed when Besu, Redis, or required storage is unavailable.

The development environment uses an environment-provided signer and master key. Production must migrate signing and key wrapping to HSM/KMS-backed services.

