#!/bin/sh
set -eu

test -s /config/genesis.json || { echo "Canonical genesis is missing. Run setup.bat first." >&2; exit 2; }
test -s /config/genesis-runtime.json || { echo "Besu runtime genesis is missing. Run setup.bat first." >&2; exit 2; }
test -s /config/permissions_config.toml || { echo "Permission configuration is missing. Run setup.bat first." >&2; exit 2; }

exec besu \
  --data-path=/var/lib/besu \
  --genesis-file=/config/genesis-runtime.json \
  --node-private-key-file=/var/lib/besu/key \
  --network-id="${CHAIN_ID}" \
  --sync-mode=FULL \
  --data-storage-format=BONSAI \
  --p2p-host="${OVERLAY_IP}" \
  --p2p-port="${P2P_PORT}" \
  --discovery-enabled=true \
  --bootnodes="${BOOTNODES}" \
  --rpc-http-enabled=true \
  --rpc-http-host=0.0.0.0 \
  --rpc-http-port=8545 \
  --rpc-http-api=ETH,NET,WEB3,QBFT,PERM,ADMIN \
  --host-allowlist=localhost,127.0.0.1,observer,agent,besu-validator-1 \
  --rpc-http-cors-origins="http://localhost:${OBSERVER_PORT}" \
  --permissions-nodes-config-file-enabled=true \
  --permissions-nodes-config-file=/config/permissions_config.toml \
  --min-gas-price=0
