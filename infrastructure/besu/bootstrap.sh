#!/usr/bin/env bash
set -euo pipefail

if [[ -f /generated/.ready ]]; then
  exit 0
fi

signer_address="${BLOCKCHAIN_SIGNER_ADDRESS#0x}"
signer_address="$(echo "$signer_address" | tr '[:upper:]' '[:lower:]')"
if [[ ! "$signer_address" =~ ^[0-9a-f]{40}$ ]]; then
  echo "BLOCKCHAIN_SIGNER_ADDRESS must be set to a valid Ethereum address before Besu initialization." >&2
  exit 1
fi

rm -rf /generated/work /generated/nodes
sed "s/\"alloc\": {}/\"alloc\": {\"${signer_address}\": {\"balance\": \"0x3635c9adc5dea00000\"}}/" \
  /network/qbftConfigFile.json > /generated/qbftConfigFile.local.json
besu operator generate-blockchain-config \
  --config-file=/generated/qbftConfigFile.local.json \
  --to=/generated/work \
  --private-key-file-name=key

mkdir -p /generated/nodes
index=1
for source in $(find /generated/work/keys -mindepth 1 -maxdepth 1 -type d | sort); do
  mkdir -p "/generated/nodes/node${index}"
  cp "$source/key" "/generated/nodes/node${index}/key"
  cp "$source/key.pub" "/generated/nodes/node${index}/key.pub"
  index=$((index + 1))
done
cp /generated/work/genesis.json /generated/genesis.json

nodes_json="["
for number in 1 2 3 4; do
  public_key=$(tr -d '\r\n' < "/generated/nodes/node${number}/key.pub" | sed 's/^0x//')
  if [[ "$number" -gt 1 ]]; then nodes_json+=","; fi
  nodes_json+="\"enode://${public_key}@172.20.0.1${number}:30303\""
done
nodes_json+="]"
printf '%s\n' "$nodes_json" > /generated/static-nodes.json

touch /generated/.ready
