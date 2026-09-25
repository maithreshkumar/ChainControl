# Database Model

Core records are users, departments, profiles, identities, identity keys, roles, permissions, role assignments, authentication challenges, assets, asset versions, transfers, blockchain transactions/events, audit events, security alerts, integrity checks, and contract deployments.

Inventory adds categories, subcategories, catalogue items, dynamic SKU variants, locations, stock balances, employee requests, reservations, and immutable movements. Stock uniqueness is `(variant, location)`. A database check prevents reserved quantity from exceeding on-hand quantity; service transactions take row locks and reject negative/oversold transitions.

Asset type is explicit. Catalogue records may be `STOCK_ITEM`, `UNIQUE_PHYSICAL_ASSET`, `DIGITAL_ASSET`, or `SOFTWARE_LICENSE`. Governed asset records use `UNIQUE_PHYSICAL_ASSET` or `DIGITAL_ASSET`; legacy `kind` remains for API compatibility during migration.

UUIDs are stable application identifiers and idempotency inputs. Blockchain transaction hash plus log index uniquely identifies an indexed event. Historical identity keys, asset versions, transactions, and audit events are append-only through application APIs.

MySQL ownership is explicitly a projection. Reconciliation compares it with `ownerOf(tokenId)` and records any repair as an audit event and alert.
