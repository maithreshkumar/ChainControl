# Network Security

## Trust boundaries

- Django is the admission authority and optional metadata service, not a consensus dependency.
- Besu peers are the blockchain data plane. Only approved enodes on the private overlay may peer.
- QBFT validators are a governed subset of approved nodes.
- Observer is read-only presentation and reads local RPC.

Enrollment tokens and node credentials use cryptographic randomness and salted Django hashes. Tokens expire and are single-use. Node credentials are scoped to their UUID. DRF throttles enrollment, status, and heartbeat. Enode/public-key/address consistency and private-overlay addresses are validated before persistence; UUID, enode, public key, and address are unique.

Private node keys stay in local Docker volumes. RPC binds to loopback on remote hosts. Observer does not proxy arbitrary JSON-RPC: a dedicated gateway permits only its exact read calls and rejects transaction, permission, admin-mutation, and validator-vote methods. Privileged RPC namespaces remain reachable only inside Docker/private management networks. Use TLS or the private overlay for Django, restrict the admin with MFA/reverse-proxy controls in production, rotate compromised enrollment/node credentials, and revoke the enode.

Audited events include enrollment, approval/rejection/revocation, offline detection, promotion/removal requests, and actual validator-set changes. Logs and API serializers exclude private keys and plaintext credentials.

Availability is fail-independent: Django loss pauses new admission/config revisions but not the chain; Observer loss does not stop Besu; full-node loss does not stop validators; validator loss is shown honestly and consensus continues only while QBFT quorum permits.
