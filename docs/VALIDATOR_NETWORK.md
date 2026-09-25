# Validator Network

Docker Compose defines four independent Hyperledger Besu 25.7 QBFT validators. Bootstrap runs `besu operator generate-blockchain-config`, creates a unique private key for each node, writes one QBFT genesis and a static peer list, and funds only the configured development governance signer. Each validator uses its own persistent data volume and fixed private-network address.

Only validator 1 exposes JSON-RPC to the host on port 8545; all nodes expose ETH, NET, QBFT, and WEB3 APIs inside the Docker network. The Observer health service queries every node for height, peer count, and validator membership. Consensus is reported healthy only when all RPCs respond, heights differ by at most one, and each reports four validators.

This topology demonstrates four-validator block production and health visibility. Do not claim production Byzantine fault tolerance from a same-host Compose test: the containers share one Docker engine and failure domain. Production needs separate hosts, protected P2P/RPC networking, durable key custody, TLS/authentication, monitoring, backups, and operational consensus-change procedures.

## Block cadence

ChainControl uses a minimum 10-second QBFT block period. Transactions arriving during a period are batched into the next block up to the block gas limit. Freshly initialized networks additionally use Besu's 60-second experimental empty-block period. QBFT does not provide an exact transaction-count trigger; consensus remains time-based so all four validators propose and finalize deterministically.

The source genesis configuration applies both values to newly initialized networks. The current Besu 25.7 chain uses a future-block transition applied consistently to all validators, preserving its history and deployed contracts. Besu 25.7 does not enforce the experimental empty-block delay through an existing-chain transition, but the verified live empty-block cadence changed from 2 seconds to approximately 14 seconds after the 10-second minimum transition.
