# Testing Strategy

- Backend: pytest + Django/DRF tests for authentication, challenge replay/expiry, RBAC scope, asset encryption/integrity, workflow transitions, idempotency, and reconciliation.
- Contracts: Hardhat + Chai tests for role enforcement, duplicate mint, governed-only transfer, freeze/archive, identity lifecycle, and pause.
- Frontend: Vitest component tests and TypeScript production builds for the business application; TypeScript production build for the separate Observer.
- Infrastructure: health checks for MySQL, Redis, MinIO, every validator, block progress, Django, and NGINX.
- Security: controlled ZAP scan and safe demonstrations for replay, projection tampering, modified object, revoked identity, unauthorized mint, and unauthorized transfer.

Nothing is marked `TESTED` in `IMPLEMENTATION_STATUS.md` until its command succeeds in the current environment.

Current regression commands:

```powershell
cd backend; py -m pytest; py manage.py check --settings=config.settings_test; py manage.py makemigrations --check --dry-run --settings=config.settings_test
cd ..\blockchain; npm test
cd ..\frontend; npm test; npm run build
cd ..\observer; npm run build
```

Live Compose validation remains separate: start all four validators, prove advancing blocks, compare membership/heights, temporarily stop one node and observe behavior, then run inventory/NFT/Observer/decryption browser journeys. A same-host Compose run does not establish production fault tolerance.
