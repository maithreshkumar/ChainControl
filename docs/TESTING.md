# Testing Strategy

- Backend: pytest + Django/DRF tests for authentication, challenge replay/expiry, RBAC scope, asset encryption/integrity, workflow transitions, idempotency, and reconciliation.
- Contracts: Hardhat + Chai tests for role enforcement, duplicate mint, freeze, owner-only transfer, identity lifecycle, and pause.
- Frontend: Vitest component tests plus Playwright role journeys.
- Infrastructure: health checks for MySQL, Redis, MinIO, every validator, block progress, Django, and NGINX.
- Security: controlled ZAP scan and safe demonstrations for replay, projection tampering, modified object, revoked identity, unauthorized mint, and unauthorized transfer.

Nothing is marked `TESTED` in `IMPLEMENTATION_STATUS.md` until its command succeeds in the current environment.

