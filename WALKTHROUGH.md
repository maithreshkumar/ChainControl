# ChainControl Walkthrough

## Architecture in one minute

Users authenticate to Django and receive a short-lived access token. Permissions are evaluated by codename and organizational scope. Sensitive actions additionally consume a signed, purpose-bound DID challenge. Files are SHA-256 hashed, encrypted with a fresh AES-256-GCM data key, and stored in MinIO. The data key is wrapped by an environment master key. Besu contracts remain authoritative for identity status, roles used by blockchain services, NFT ownership, freeze state, and immutable events. Celery tracks receipts, indexes events, and reconciles MySQL projections.

## Prepare the demo

Follow `README.md` through environment setup, validator startup, contract deployment, deployment import, role seeding, and platform Admin bootstrap. Create separate browser-wallet accounts for Alice and Bob; never use governance or validator keys as user demo keys.

Open the business app at `http://localhost/` and the independent read-only Observer at `http://localhost:5174/`. Sign in to Observer using an Admin, Validator, Manager, or Auditor account whose seeded role includes `observer.view`.

## Demonstrate independent node synchronization

1. As Django superuser, open `/admin/network/`, create an expiring enrollment code, and give it with the private ChainControl URL to the remote operator.
2. On a second overlay-connected Windows computer, run the generated package's `scripts\setup.bat`. Confirm the PENDING node and that no private key appears in Django.
3. Approve it in Network Administration. Start the package and open its `http://localhost:5174`.
4. Compare the local head/hash with the main node. Create a normal ChainControl transaction and watch the new block arrive without copying data files.
5. Stop the remote package, allow the network to advance, restart it, and watch real sync progress reach the current head.
6. Disconnect Django temporarily: existing Besu synchronization and local raw block viewing must continue. Do not claim geographic decentralization until this is executed on a physically separate host.

## Catalogue and request inventory

1. In Django Admin, create a category, optional subcategory, catalogue item, SKU variant, location, and stock record.
2. Receive stock using the stock API/admin-authorized workflow so an append-only movement is created.
3. As an employee, open **Inventory**, filter by hardware/software or search SKU, and request an available quantity.
4. As Manager/Admin, open **Requests**, reserve/approve, issue, reject, or later return it.
5. Observe available, reserved, on-hand, and issued quantities update without becoming negative.

## Onboard Alice

1. Sign in as the platform Admin.
2. Request an `IDENTITY_CHANGE` DID challenge and sign it with the Admin controller.
3. Create an invitation with Alice’s email, employee ID, department, and USER role.
4. Give Alice the one-time activation token through a controlled demo channel.
5. Alice activates with a strong password. Django administration provisions her encrypted controller wallet; the user cannot create their own key.
6. A validator approves the pending DID. Wait for the `IdentityRegistered` receipt/event; the identity becomes `ACTIVE` only after confirmation.

## Register and mint a digital asset

1. Open Asset Registry as Admin and choose **Register asset**.
2. Select a test file, classification, department, and owner.
3. Sign the `ASSET_MINT` challenge.
4. Observe `PROCESSING` then `BLOCKCHAIN_PENDING`; no completed state is shown early.
5. After the `AssetMinted` event is indexed, the asset becomes `ACTIVE` with its real token ID.

The MinIO object contains ciphertext. MySQL contains metadata, wrapped key material, and a projection. The `AssetRegistry` contains the authoritative content/metadata hashes and ownership.

## Transfer Alice’s asset to Bob

1. Alice signs an `ASSET_TRANSFER` challenge and creates a transfer request.
2. Bob accepts it.
3. A scoped Manager who is neither sender nor recipient signs an `ASSET_TRANSFER` challenge and approves.
4. The backend submits `governedTransfer` through the authorized transfer agent.
5. Only after confirmation does the projection change to Bob and the request become `COMPLETED`.

The API actions are `/transfers/{id}/accept/`, `/reject/`, and `/approve/`. The contract rejects direct owner transfer calls; only the authorized transfer agent can execute the confirmed governed transfer.

## Verify integrity

Call `/assets/{id}/verify/` as an authorized user. ChainControl retrieves and authenticates the encrypted object, recomputes SHA-256, and records an integrity check. AES-GCM tag failure or hash mismatch creates a `FILE_INTEGRITY_FAILURE` alert; the application never rewrites the authoritative hash to hide the mismatch.

## Safe security demonstrations

- Replay: submit the same challenge twice. The second attempt returns `CHALLENGE_ALREADY_USED`.
- Revoked identity: revoke a test identity, then submit a signature made by its old valid key. It is denied because state is not ACTIVE.
- Unauthorized mint: call asset creation as USER. Backend permission denies it; contract tests also prove unauthorized callers revert.
- Projection tamper: in a disposable test database only, alter an asset owner projection. Run reconciliation; it creates a critical alert and repairs to a known on-chain identity.
- Object tamper: alter only a disposable MinIO object copy. Integrity verification fails and preserves the evidence.
- Frozen transfer: freeze a disposable NFT, then attempt transfer. `AssetRegistry` reverts.

## Audit and health

Open Observer to inspect incrementally loaded blocks, full transactions, decoded calls/events, NFT owner projections, analytics, search, and the live dynamically discovered validator set. It polls real endpoints every five seconds and contains no fake activity.

## Authorized decryption demonstration

Run `python manage.py decrypt_asset ASSET_UUID --actor admin --reason "Approved demo recovery" --output /tmp/recovered.bin` inside the backend container. Confirm the audit trail contains `ADMIN_DECRYPT`, inspect the file only for the approved purpose, then delete it. Use `--cleanup` only when immediate automatic deletion is explicitly desired.

## Current demonstration boundary

Backend unit/security tests, both frontend production builds, and Hardhat contract tests pass. Treat `docs/IMPLEMENTATION_STATUS.md` as authoritative for the remaining live multi-container verification boundary.
