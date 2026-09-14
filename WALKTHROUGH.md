# ChainControl Walkthrough

## Architecture in one minute

Users authenticate to Django and receive a short-lived access token. Permissions are evaluated by codename and organizational scope. Sensitive actions additionally consume a signed, purpose-bound DID challenge. Files are SHA-256 hashed, encrypted with a fresh AES-256-GCM data key, and stored in MinIO. The data key is wrapped by an environment master key. Besu contracts remain authoritative for identity status, roles used by blockchain services, NFT ownership, freeze state, and immutable events. Celery tracks receipts, indexes events, and reconciles MySQL projections.

## Prepare the demo

Follow `README.md` through environment setup, validator startup, contract deployment, deployment import, role seeding, and platform Admin bootstrap. Create separate browser-wallet accounts for Alice and Bob; never use governance or validator keys as user demo keys.

## Onboard Alice

1. Sign in as the platform Admin.
2. Request an `IDENTITY_CHANGE` DID challenge and sign it with the Admin controller.
3. Create an invitation with Alice’s email, employee ID, department, and USER role.
4. Give Alice the one-time activation token through a controlled demo channel.
5. Alice activates with a strong password and her controller address.
6. Wait for the `IdentityRegistered` receipt/event. Alice’s application identity changes from `INVITED` to `ACTIVE` only after confirmation.

The frontend invitation form is not yet implemented; use the documented REST endpoints until the implementation status marks it complete.

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

The API actions are `/transfers/{id}/accept/`, `/reject/`, and `/approve/`. Dedicated frontend action controls remain in progress.

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

Auditors can inspect `/audit/`, `/security-alerts/`, `/blockchain/transactions/`, and `/blockchain/events/`. Admins can inspect `/blockchain/health/`, which performs live RPC checks against all four validators and reports actual block heights.

## Current demonstration boundary

Backend unit/security tests, frontend build/tests, and Hardhat contract tests pass. The complete Compose E2E path has not been executed in this workspace because Docker is absent. Treat `docs/IMPLEMENTATION_STATUS.md` as authoritative before presenting any flow as verified.

