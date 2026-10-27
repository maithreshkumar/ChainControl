# Validator Network

Docker Compose retains four independent Hyperledger Besu 25.7 validators as the initial development bootstrap set. Bootstrap runs `besu operator generate-blockchain-config`, creates a unique private key for each initial node, writes one QBFT genesis and peer/permission files, and funds only the configured development governance signer. Each initial validator uses its own persistent data volume and private-network address. This initial count is configurable and is not the permanent application topology.

The managed RPC list is environment-driven. Health queries every configured endpoint for height, peer count, and the actual validator set; consensus health requires reachable configured nodes, near-equal heights, a non-empty validator set, and matching reported membership. It never requires a literal count of four.

Approved remote nodes join as independently keyed full nodes over a private overlay. Validator promotion/removal requires real QBFT votes and actual-set verification. Remote validator agents can cast a locally delivered pending vote without publishing their management RPC. See `VALIDATOR_GOVERNANCE.md` and `NETWORK_PERMISSIONING.md`.

The four initial containers share one Docker engine and failure domain, so they do not prove geographic decentralization or production fault tolerance. Production needs separate hosts, protected P2P/management networking, durable key custody, TLS/authentication, monitoring, backups, and consensus-change procedures.

## Block cadence

ChainControl uses a minimum 10-second QBFT block period. Transactions arriving during a period are batched into the next block up to the block gas limit. Freshly initialized networks additionally use Besu's 60-second experimental empty-block period. QBFT does not provide an exact transaction-count trigger; consensus remains time-based and the current governed validator set proposes/finalizes blocks.

The source genesis configuration applies both values to newly initialized networks. The current Besu 25.7 chain uses a future-block transition applied consistently to all validators, preserving its history and deployed contracts. Besu 25.7 does not enforce the experimental empty-block delay through an existing-chain transition, but the verified live empty-block cadence changed from 2 seconds to approximately 14 seconds after the 10-second minimum transition.
