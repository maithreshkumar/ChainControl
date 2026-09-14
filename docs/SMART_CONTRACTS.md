# Smart Contracts

`TrustAccessManager` uses OpenZeppelin `AccessControl` and exposes identity-admin, access-admin, asset-minter, transfer-agent, auditor, and emergency-admin roles.

`IdentityRegistry` stores only hashed DID references, controller addresses, state, and key versions. Registration, suspension, revocation, activation, and rotation emit events.

`AssetRegistry` is an ERC-721 contract. Minting is restricted, application asset IDs are unique, frozen assets cannot transfer, and asset/content proof remains queryable. Direct transfers use standard ownership checks. The platform transfer state machine submits `governedTransfer` through the narrowly authorized transfer-agent role after recipient acceptance and scoped approval.

The deployer bootstraps governance. Deployment scripts grant contract roles explicitly; Django superuser status has no relation to them.
