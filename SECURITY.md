# Security Policy

Do not report suspected vulnerabilities through public demo data or commit secrets as proof. Preserve the correlation ID, affected endpoint/transaction, approximate time, and minimal reproduction steps, then disclose privately to the project maintainers.

Never commit `.env`, private keys, plaintext asset keys, passwords, production credentials, real employee data, or confidential files. The development governance signer and file-wrapping key are disposable local credentials only. Production deployments must use managed secrets, HSM/KMS signing and key wrapping, TLS, validator isolation, monitoring, backups, and a formal incident-response process.

The separate Observer is read-only and permissioned. Administrative asset recovery requires a named authorized actor and reason, verifies AES-GCM plus SHA-256, writes only to an explicit restricted path, and records success/failure without logging keys. In the demo, MinIO storage administration and decryption authority may share an operator; production must separate those roles.

Security-sensitive design and known residual risks are documented in [docs/SECURITY.md](docs/SECURITY.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md). Current implementation boundaries are tracked in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).
