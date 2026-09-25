# Smart Contracts

`TrustAccessManager` uses OpenZeppelin `AccessControl` and exposes identity-admin, access-admin, asset-minter, transfer-agent, auditor, and emergency-admin roles.

`IdentityRegistry` stores only hashed DID references, controller addresses, state, and key versions. Registration, suspension, revocation, activation, and rotation emit events.

`AssetRegistry` is a real OpenZeppelin ERC-721 contract. Minting is restricted, application asset IDs are unique, frozen or archived assets cannot transfer, and asset/content proof remains queryable. `_update` requires `TRANSFER_AGENT_ROLE` for every non-mint/non-burn ownership change, so an owner cannot bypass the governed workflow with `transferFrom` or `safeTransferFrom`. The platform state machine submits `governedTransfer` only after recipient acceptance and scoped approval. Freeze, unfreeze, archive, mint, and governed transfer emit explicit events.

The deployer bootstraps governance. Deployment scripts grant contract roles explicitly; Django superuser status has no relation to them.
