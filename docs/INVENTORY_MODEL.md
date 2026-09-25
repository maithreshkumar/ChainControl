# Inventory Model

Catalogue structure is Category → optional Subcategory → Item → Variant/SKU. Items carry one explicit type: `STOCK_ITEM`, `UNIQUE_PHYSICAL_ASSET`, `DIGITAL_ASSET`, or `SOFTWARE_LICENSE`. Variant-specific properties such as dimensions, connector type, edition, or license term live in validated JSON attributes without forcing a new table per category.

Stock is per `(variant, location)` and tracks on-hand, reserved, and issued quantities; available is `on_hand - reserved`. All mutations use database transactions and row locks. Reservations cannot exceed on-hand stock, quantities cannot be negative, and every receive/reserve/release/issue/return/transfer/adjust action creates an immutable movement plus an audit event.

Employees can browse/search/filter availability and create/cancel their own requests. Scoped Managers/Admins can reserve/approve, reject, issue, and return. Catalogue and stock administration require separate permission codes. The Django Admin provides catalogue maintenance; blockchain and audit records remain read-only there.

Quantity inventory is not tokenized merely for being inventory. Only uniquely governed assets move into the Asset/NFT lifecycle; quantity software licenses can remain normal stock.
