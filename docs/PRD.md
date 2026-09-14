# ChainControl Product Requirements

ChainControl is an enterprise identity and asset-governance platform for SIH26125. It provides controlled onboarding, `did:ethr`-style identities, permission-level RBAC, unique ERC-721 assets, governed custody transfers, encrypted digital-file storage, and immutable blockchain evidence.

The visible roles are Admin, Manager, Auditor, and User. A Django superuser is a technical operator and receives no blockchain authority by implication.

## Required outcome

The reference scenario is: an Admin invites Alice, Alice activates and proves control of her DID key, an encrypted file is registered and minted as an NFT, Alice requests transfer to Bob, Bob accepts, a Manager approves, Besu confirms ownership, the indexed projection changes, and the full history is auditable.

## Trust boundaries

- MySQL stores operational state and searchable projections.
- MinIO stores AES-256-GCM encrypted content.
- Besu and contracts are authoritative for identity status, security roles, asset proof, and ownership.
- React is an untrusted client. Django and contracts independently authorize operations.

## Non-goals

This is not an NFT marketplace, cryptocurrency product, public signup service, Merkle-tree substitute for blockchain, or AI system.

