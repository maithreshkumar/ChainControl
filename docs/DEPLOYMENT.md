# Deployment

Development uses Docker Compose for MySQL, Redis, MinIO, four independent Besu QBFT validator services/volumes, Django, Celery, the business React app, the Observer React app, and NGINX. Besu bootstrap generates disposable validator keys into a Docker volume; these keys are not production credentials. The business app is served on port 80, Observer on 5174, MinIO Console on 9001, and validator-1 JSON-RPC on 8545.

Production requires separate hosts/failure domains for validators, TLS everywhere, secrets in a KMS/secret manager, HSM/KMS transaction signing, private networking, database backups, MinIO replication/versioning, monitoring, rate limiting, and image pinning/signature verification.

For a real deployment, expose only controlled reverse proxies. MySQL, Redis, MinIO API, backend, validator peer/RPC interfaces, and administrative recovery tooling remain private. The prototype Observer trusts the same JWT issuer and internal role database as the business app; put it behind internal access controls and TLS.

## Remote Besu nodes

The `node-package/` build produces a Windows-first archive that joins the same chain using the byte-identical registered genesis. It generates a unique node key locally, requests admission, binds P2P to a private overlay IP, binds RPC/Observer to loopback, and persists chain data in a named volume. Refer to `REMOTE_NODE_SETUP.md` and `NODE_PACKAGE.md`.

Migration is non-destructive: first back up the existing Besu volumes, register the exact mounted genesis, register current bootstrap nodes, enable permissioning one validator at a time, and confirm height/peer/validator-set after every restart. Never use `docker compose down --volumes` on the main project. The local node package's explicitly named development reset is unrelated to main deployment data.
