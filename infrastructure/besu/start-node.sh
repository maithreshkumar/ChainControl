#!/usr/bin/env bash
set -euo pipefail

node_number="$1"
cp /generated/static-nodes.json /data/static-nodes.json

exec besu \
  --data-path=/data \
  --genesis-file=/generated/genesis.json \
  --node-private-key-file="/generated/nodes/node${node_number}/key" \
  --p2p-host=0.0.0.0 \
  --p2p-port=30303 \
  --rpc-http-enabled=true \
  --rpc-http-host=0.0.0.0 \
  --rpc-http-port=8545 \
  --rpc-http-api=ETH,NET,QBFT,WEB3 \
  --host-allowlist='*' \
  --rpc-http-cors-origins='*' \
  --min-gas-price=0 \
  --sync-mode=FULL

