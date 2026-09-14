# Security Policy

Do not report suspected vulnerabilities through public demo data or commit secrets as proof. Preserve the correlation ID, affected endpoint/transaction, approximate time, and minimal reproduction steps, then disclose privately to the project maintainers.

Never commit `.env`, private keys, plaintext asset keys, passwords, production credentials, real employee data, or confidential files. The development governance signer and file-wrapping key are disposable local credentials only. Production deployments must use managed secrets, HSM/KMS signing and key wrapping, TLS, validator isolation, monitoring, backups, and a formal incident-response process.

Security-sensitive design and known residual risks are documented in [docs/SECURITY.md](docs/SECURITY.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md). Current implementation boundaries are tracked in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

