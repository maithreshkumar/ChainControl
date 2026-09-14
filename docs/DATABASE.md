# Database Model

Core records are users, departments, profiles, identities, identity keys, roles, permissions, role assignments, authentication challenges, assets, asset versions, transfers, blockchain transactions/events, audit events, security alerts, integrity checks, and contract deployments.

UUIDs are stable application identifiers and idempotency inputs. Blockchain transaction hash plus log index uniquely identifies an indexed event. Historical identity keys, asset versions, transactions, and audit events are append-only through application APIs.

MySQL ownership is explicitly a projection. Reconciliation compares it with `ownerOf(tokenId)` and records any repair as an audit event and alert.

