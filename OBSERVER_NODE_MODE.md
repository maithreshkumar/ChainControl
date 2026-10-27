# Observer Local-Node Mode

When built with `VITE_LOCAL_RPC_URL=/rpc/`, Observer enters local-node mode. NGINX proxies `/rpc/` through a strict read-only gateway to the package's Besu container. Chain blocks, transaction/receipt fields, validator set, local head, peers, and sync state are read from that local node; no Django login is needed because the service is loopback-only.

`/node-config.json` is produced by the node agent and adds node name, UUID, governed role, status, network head, sync percentage, peer count, and enode. It contains no private key or API credential.

The distribution includes the existing chain-1337 deployment ABI bundle. Local transaction input and receipt logs are decoded into contract, function, parameters, and events when their target/log address matches that bundle. Local mode remains usable when Django is down. Raw blockchain fields and ABI decoding continue to work. **Connect metadata** optionally authenticates to central Django through a gateway limited to token, current-user, search, NFT, and analytics reads; disconnecting or losing Django simply hides those enrichment tabs. Central Observer mode retains authenticated business metadata/search/NFT/analytics views.

The node package publishes Observer only on `127.0.0.1:5174`. If remote viewing is required, use an authenticated TLS reverse proxy on the private overlay; do not change it to an unrestricted public bind.
