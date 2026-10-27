#!/usr/bin/env bash
set -euo pipefail

write_permissions_file() {
  mkdir -p /generated/runtime
  if [[ ! -f /generated/runtime/permissions_config.toml ]]; then
    if [[ -f /generated/permissions_config.toml ]]; then
      cp /generated/permissions_config.toml /generated/runtime/permissions_config.toml
    elif [[ -f /generated/static-nodes.json ]]; then
      sed '1s/^/nodes-allowlist=/' /generated/static-nodes.json > /generated/runtime/permissions_config.toml
      printf '\naccounts-allowlist=[]\n' >> /generated/runtime/permissions_config.toml
    fi
  fi
  chown 10001:10001 /generated/runtime
  chmod 755 /generated/runtime
  if [[ -f /generated/runtime/permissions_config.toml ]]; then
    chown 10001:10001 /generated/runtime/permissions_config.toml
    chmod 644 /generated/runtime/permissions_config.toml
  fi
}

if [[ -f /generated/.ready ]]; then
  write_permissions_file
  exit 0
fi

signer_address="${BLOCKCHAIN_SIGNER_ADDRESS#0x}"
signer_address="$(echo "$signer_address" | tr '[:upper:]' '[:lower:]')"
if [[ ! "$signer_address" =~ ^[0-9a-f]{40}$ ]]; then
  echo "BLOCKCHAIN_SIGNER_ADDRESS must be set to a valid Ethereum address before Besu initialization." >&2
  exit 1
fi

rm -rf /generated/work /generated/nodes
initial_validator_count="${INITIAL_VALIDATOR_COUNT:-4}"
if [[ ! "$initial_validator_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "INITIAL_VALIDATOR_COUNT must be a positive integer." >&2
  exit 1
fi

sed -e "s/\"alloc\": {}/\"alloc\": {\"${signer_address}\": {\"balance\": \"0x3635c9adc5dea00000\"}}/" \
    -e "s/\"count\": [0-9][0-9]*/\"count\": ${initial_validator_count}/" \
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
for number in $(seq 1 "$initial_validator_count"); do
  public_key=$(tr -d '\r\n' < "/generated/nodes/node${number}/key.pub" | sed 's/^0x//')
  if [[ "$number" -gt 1 ]]; then nodes_json+=","; fi
  node_ip=$((10 + number))
  nodes_json+="\"enode://${public_key}@172.20.0.${node_ip}:30303\""
done
nodes_json+="]"
printf '%s\n' "$nodes_json" > /generated/static-nodes.json
write_permissions_file

touch /generated/.ready
