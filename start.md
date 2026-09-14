# Now, how do I start my service?

All first-time bootstrap steps (genesis initialization, smart contract deployment, role seeding, and administrator creation) are complete. Starting ChainControl is now a single command.

---

## 1. Start the Platform

Open PowerShell in the project directory (`C:\Users\Maithresh\Desktop\SIH26125\ChainControl`) and run:

```powershell
docker compose up -d --build
```

This starts all services in the background:
- **MySQL 8.4** (Database)
- **Redis 7.4** (Cache & Task Broker)
- **MinIO** (Encrypted Object Storage)
- **4 Hyperledger Besu Validators** (Private QBFT Consensus Network)
- **Django REST Framework** (Backend API & Gunicorn)
- **Celery Worker & Celery Beat** (Receipt indexing & reconciliation)
- **React Client & NGINX** (Web UI & Reverse Proxy)

---

## 2. Verify Service Status

Check that all containers are running and healthy:

```powershell
docker compose ps
```

To verify live block production on the blockchain:

```powershell
Invoke-RestMethod -Uri http://localhost:8545 -Method Post -ContentType application/json -Body '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

---

## 3. Access ChainControl

Open your browser and navigate to:

| Interface | URL | Credentials / Information |
| :--- | :--- | :--- |
| **ChainControl Governance Web App** | [http://localhost/](http://localhost/) | **Username**: `user`<br>**Password**: `user` |
| **Validator Workspace** | [http://localhost/validator](http://localhost/validator) | **Username**: `validator`<br>**Password**: `validator` |
| **Django Administration Portal** | [http://localhost/admin/](http://localhost/admin/) | **Username**: `admin`<br>**Password**: `AdminPassword123!` |
| **MinIO Console** | [http://localhost:9001/](http://localhost:9001/) | **Username**: `minioadmin`<br>**Password**: `minioadmin` |
| **Hyperledger Besu RPC** | [http://localhost:8545/](http://localhost:8545/) | JSON-RPC Endpoint (Chain ID `1337`) |

## 4. Issue Controller Wallets from Django Administration

Users and validators cannot create, import, replace, or generate controller wallets. Only Django administration can issue an approved encrypted keystore.

1. Open [http://localhost/admin/](http://localhost/admin/) and sign in as the Django administrator.
2. Open **Accounts → Wallet provisions → Add wallet provision**.
3. Select the application account.
4. For a newly activated account with no DID, select **Generate a new controller key** and leave **Controller private key** empty. Django creates the key, the pending DID, and the encrypted wallet together.
5. For an existing account that already has a DID, leave **Generate a new controller key** clear and enter the private key matching its current controller address.
6. Create a **Wallet access code** containing at least 12 characters.
7. Save the provision and give only the access code to the account holder through an approved channel. Never give them the private key.

For this local demonstration, Django administration uses the following controller data:

| Account | Admin-only local-development private key | Required controller address |
|---|---|---|
| `user` | `0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6` | `0x90F79bf6EB2c4f870365E785982E1f101E93b906` |
| `validator` | `0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a` | `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC` |

For newly generated controllers, the key is created inside the Django administration workflow and immediately encrypted. For existing controllers, the supplied private key is used only while Django creates the encrypted keystore. ChainControl stores the encrypted keystore and a one-way digest of the access code; it does not store the plaintext private key or plaintext access code.

An invited person can set their account password, but cannot submit a controller address or create a wallet during invitation activation. Their account remains **AWAITING_ADMIN_PROVISION** until Django administration adds its wallet provision. A newly generated DID then remains **VALIDATION_PENDING** until a validator approves it.

To reissue access, edit the account's **Wallet provision**, enter the matching private key and a new access code, and save. The account cannot be moved to a different controller from this screen, and reissuing resets the previous claim workflow.

---

## 5. Configure the Validator Account

The validator account has already been created:

```text
Username: validator
Password: validator
```

Then:

1. Sign out of the `user` account.
2. Sign in with username `validator` and password `validator`.
3. Open **Wallet** and enter the one-time access code issued by Django administration.
4. Claim and unlock the encrypted controller wallet.
5. Open [http://localhost/validator](http://localhost/validator).

Normal users submit registrations from **Asset Registry** using **Verify DID & submit**. The asset stays `BLOCKCHAIN_PENDING` and appears in the Validator Workspace. Only the validator can press **Validate & activate**. New DID registrations similarly stay `VALIDATION_PENDING` until a validator presses **Validate DID**.

The Asset Registry also provides **Refresh blockchain**. It manually queues an immediate receipt check and refreshes the asset list. This can update a pending token confirmation, but it does not replace validator approval. Browser refreshes now preserve the signed-in session and keep the current route, including `/assets`.

> The `user`/`user` and `validator`/`validator` credentials and the administrator-only demonstration keys are for local use only. Replace them before using ChainControl outside this isolated development environment.

---

## 6. View Logs

To inspect live logs across the application stack:

```powershell
# Follow logs for all services
docker compose logs -f

# Follow logs for specific services
docker compose logs -f backend celery-worker besu-validator-1
```

*(Press `Ctrl + C` to exit the log view. This will not stop the running containers.)*

---

## 7. Stop the Services

When you are done, stop all containers while preserving all blockchain history, database state, and encrypted files:

```powershell
docker compose down
```

---

## 8. Complete Reset (Optional / Destructive)

Only use this if you want to wipe all local data and start completely fresh:

> **Permanent data-loss warning:** `docker compose down -v`, Docker Desktop **Clean / Purge data**, and Docker volume-pruning commands delete the MySQL, MinIO, and blockchain volumes. Normal shutdown must use only `docker compose down`.

```powershell
# Wipes all database, blockchain, and MinIO storage volumes
docker compose down -v
```
