# Implementation Status

Status reflects executed evidence on 15 September 2026 IST. `TESTED` is used only where the named automated or live command passed.

| Area | Status | Evidence / remaining boundary |
|---|---|---|
| Repository audit and upgrade plan | TESTED | `UPGRADE_ANALYSIS.md`; migrations and Django checks executed |
| Enterprise inventory model and APIs | TESTED | Atomic movement/request tests including oversell, scope, catalogue, issue and return |
| Main inventory and request UI | TESTED | Main React production build and existing Vitest suite pass |
| Asset-type separation/migration | TESTED | Migration check and backend regression suite pass |
| ERC-721 governance hardening | TESTED | Hardhat tests prove mint authorization, direct-transfer rejection, governed transfer, freeze/archive restrictions |
| NFT backend/UI projection | TESTED | Updated contracts deployed at live block 7496; active ABI includes archive/unfreeze governance and the projection tests pass |
| Four-validator Besu QBFT topology | TESTED | All four independent validator containers are healthy and the live health API reports consensus with synchronized heights |
| Observer backend | TESTED | Permission, pagination, read-only method, decoded transaction tests, and live QBFT block reads pass |
| Separate Observer React app | TESTED | Production TypeScript/Vite build passes; live app and its authenticated API return successfully on port 5174 |
| Live validator/network visualization | TESTED | Live health response contains four validators, real QBFT heights, and `consensus_healthy=true` |
| Encrypted MinIO storage | TESTED | Existing AES-256-GCM round-trip, SHA-256, and tamper rejection test passes |
| Administrative decryption utility | TESTED | Valid output, invalid UUID, authenticated failure, audit, no-key logging, and explicit cleanup tests pass |
| Docker Compose live smoke test | TESTED | All 13 long-running services are up; main app, admin, observer, MinIO, auth, inventory, RPC, migrations, and live observer reads passed |

## Decentralization upgrade — 25 September 2026 IST

| Area | Status | Evidence / remaining boundary |
|---|---|---|
| Repository audit and migration plan | IMPLEMENTED | `DECENTRALIZATION_UPGRADE_PLAN.md`; chain ID 1337 and existing contract anchors recorded; no chain data changed |
| Dynamic node registry/enrollment | TESTED | Token, identity validation, scoped credential, admission and rejection unit tests pass |
| Besu permission propagation | PARTIALLY LIVE TESTED | All four preserved validators report the same enforced four-enode allowlist; add/remove failure semantics pass unit tests; remote mutation acceptance remains |
| QBFT promotion/removal | TESTED (MOCKED) | Tests prove projection changes only after actual-set response and final validator is protected; live votes not executed |
| Windows remote-node package | BUILD + KEYGEN TESTED | Self-contained archive and all images build; temporary-volume smoke test generated a unique 128-hex public key/address and cleaned up; remote enrollment remains |
| Local Observer mode | LIVE TESTED | Local block reads and ABI bundle load; browser write/vote RPC is rejected 403; optional metadata requires authentication and degrades independently |
| Live chain preservation | TESTED | Existing volumes retained; chain 1337 reached block 8587; canonical genesis SHA-256 is `f7c74cf20c85e0281ae1bf7508c761dccace45ac88526b0483e1370bc789b106`; deployed contract code remains present |
| Dynamic global health/topology | LIVE TESTED | Four managed validators ONLINE at identical height with three peers each, matching actual validator set, healthy consensus, and six observed non-fabricated topology edges |

This upgrade does not yet claim physical geographic decentralization. That claim requires the documented physically separate overlay-host enrollment/sync/reconnect/revocation test, followed by controlled live validator add/remove voting. The previously reported business tests remain historical evidence; the complete backend regression suite currently passes (`58 passed`), both React production builds pass, the Observer production dependency audit reports zero vulnerabilities, both Compose definitions validate, and Django reports no model drift.
