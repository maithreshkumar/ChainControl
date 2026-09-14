# ChainControl

ChainControl is a blockchain-backed identity, access-control, and digital-asset governance platform for SIH26125. It combines Django 6.1, DRF, React/TypeScript, MySQL, Redis/Celery, encrypted MinIO objects, three Solidity contracts, and one four-validator Hyperledger Besu QBFT network.

The repository currently implements and tests the security foundation and its first vertical slices. See [implementation status](docs/IMPLEMENTATION_STATUS.md) for the exact boundary; do not treat unchecked infrastructure or incomplete workflows as production-ready.

## Prerequisites

- Docker Desktop with Docker Compose v2 (required for the integrated stack)
- Node.js 22.13+ and npm (only needed for host-side frontend/contract development)
- Python 3.14 and MySQL build prerequisites (only needed for host-side backend development)
- A browser wallet capable of `personal_sign` for DID step-up authorization

Docker was not installed on the machine where this repository was initially generated, so the complete Compose topology still requires first-run verification on a Docker-capable host.

## Environment configuration

Copy `.env.example` to `.env` and replace every `replace-*` value. Never commit `.env`.

Generate a Django secret and an asset master key:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Generate a disposable development governance signer:

```powershell
python -c "from eth_account import Account; a=Account.create(); print('ADDRESS='+a.address); print('PRIVATE_KEY='+a.key.hex())"
```

Put the address and private key in `BLOCKCHAIN_SIGNER_ADDRESS` and `BLOCKCHAIN_SIGNER_PRIVATE_KEY`. This development signer bootstraps contract governance and submits backend transactions. Production must use HSM/KMS-backed signing.

## Start infrastructure

```powershell
docker compose up -d mysql redis minio besu-bootstrap besu-validator-1 besu-validator-2 besu-validator-3 besu-validator-4
docker compose ps
```

The four validator services maintain one chain (chain ID 1337). Besu RPC is exposed at `http://localhost:8545`. MinIO Console is exposed at `http://localhost:9001`.

Verify block production:

```powershell
Invoke-RestMethod -Uri http://localhost:8545 -Method Post -ContentType application/json -Body '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

## Compile, test, and deploy contracts

Host-side development:

```powershell
cd blockchain
npm install
npm run compile
npm test
cd ..
```

Deploy through Docker using the signer in `.env`:

```powershell
docker compose --profile tools run --rm contract-deployer
```

This writes `blockchain/deployments/1337.json`. Import the verified ABI/address metadata after starting the backend:

```powershell
docker compose up -d backend
docker compose exec backend python manage.py import_contract_deployments /deployments/1337.json
```

## Database and bootstrap

The backend container applies migrations on startup. Seed granular roles and permissions:

```powershell
docker compose exec backend python manage.py seed_roles
```

Create a technical Django operator (this grants no platform or blockchain authority):

```powershell
docker compose exec backend python manage.py createsuperuser
```

Create the first business Admin using that person’s wallet/controller address:

```powershell
docker compose exec backend python manage.py bootstrap_platform_admin --username admin --email admin@example.test --employee-id EMP-001 --department GOVERNANCE --controller-address 0xYOUR_ADDRESS
```

Run the receipt tracker once if you do not want to wait for Celery Beat:

```powershell
docker compose exec backend python manage.py shell -c "from apps.blockchain.tasks import track_pending_transactions; track_pending_transactions()"
```

## Start the complete application

```powershell
docker compose up -d backend celery-worker celery-beat frontend nginx
docker compose ps
```

- Application: `http://localhost/`
- Django Admin: `http://localhost/admin/`
- MinIO Console: `http://localhost:9001/`
- Besu JSON-RPC: `http://localhost:8545/`
- Internal explorer APIs: `http://localhost/api/v1/blockchain/transactions/` and `/events/`

## Host-side development

Backend tests use isolated SQLite settings and do not substitute for MySQL integration tests:

```powershell
cd backend
python -m pip install -r requirements.txt
python manage.py check --settings=config.settings_test
python -m pytest
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
npm run build
npm test
```

If a restricted Windows environment prevents Vite from loading its config, use the repository scripts, which invoke Vite’s runner-based config loader for build/test/preview.

## API and onboarding

APIs are under `/api/v1/`. Obtain a JWT at `/auth/token/`. An Admin creates an invitation at `/invitations/` after a purpose-bound `IDENTITY_CHANGE` DID proof. The recipient activates once through `/invitations/activate/`; identity registration is then submitted to Besu and remains `INVITED` until its event is confirmed and indexed.

High-risk requests obtain and sign a challenge through `/auth/challenges/` and `/auth/challenges/verify/`, then send the one-use proof in `X-DID-Proof-Token`.

## Run all available tests

```powershell
cd backend
python -m pytest
cd ..\blockchain
npm test
cd ..\frontend
npm run build
npm test
```

## Stop and clean development services

Stop without deleting data:

```powershell
docker compose down
```

Delete disposable local containers and named volumes only when you intentionally want a clean chain/database/object store:

```powershell
docker compose down --volumes --remove-orphans
```

This volume-removal command is destructive and cannot recover prior local chain or database state.

## Documentation

Start with [architecture](docs/ARCHITECTURE.md), [security design](docs/SECURITY.md), [threat model](docs/THREAT_MODEL.md), [API](docs/API.md), and the [demo walkthrough](WALKTHROUGH.md).

