# Observer Architecture

The Observer is a separately built React application served at `http://localhost:5174/`. Its NGINX proxies `/api/` to Django, but the UI calls only JWT identity, Observer, and blockchain-health GET endpoints. `observer.view` is seeded for Admin, Validator, Manager, and Auditor; User does not receive it.

The block feed reads Besu directly and loads at most 50 records per request, newest first, with `before` pagination. A five-second poll discovers a new head. Block detail includes hashes, parent, proposer, gas, timestamp, finality projection, and real transactions. Transaction detail reads the receipt, decodes ABI input/events from active contract deployments, and enriches it with indexed DID/asset/transfer context where available.

NFT explorer data comes from confirmed MySQL projections and links token IDs to owner DID, department, lifecycle, integrity checks, and governed-transfer counts. Analytics are database aggregations plus the current Besu height. Network status calls every configured validator for block height, peer count, and the QBFT validator set.

This is an internal demonstration console, not a public block explorer. It trusts Django JWT/RBAC, deployment ABIs, and the configured private RPC endpoints. It never returns wallet files, private keys, wrapped keys, MinIO credentials, plaintext assets, or mutation controls.
