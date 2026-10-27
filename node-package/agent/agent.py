"""ChainControl node control-plane agent.

Uses only the Python standard library. It never reads or transmits the Besu
private key. The only secret it reads is the scoped Django node credential.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


API_URL = os.environ["CHAINCONTROL_API_URL"].rstrip("/")
NODE_UUID = os.environ["NODE_UUID"]
NODE_VERSION = os.getenv("NODE_VERSION", "1.0.0")
RPC_URL = os.getenv("BESU_RPC_URL", "http://besu-validator-1:8545")
CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/config"))
CREDENTIAL_FILE = Path(os.getenv("NODE_CREDENTIAL_FILE", "/run/secrets/node_credential"))
POLL_SECONDS = max(5, int(os.getenv("POLL_SECONDS", "15")))


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def credential() -> str:
    return CREDENTIAL_FILE.read_text(encoding="utf-8").strip()


def api(path: str, *, method: str = "GET", payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=body,
        method=method,
        headers={"Authorization": f"Node {credential()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def rpc(method: str, params=None):
    request = urllib.request.Request(
        RPC_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        result = json.load(response)
    if result.get("error"):
        raise RuntimeError(f"{method}: {result['error']}")
    return result.get("result")


def hex_int(value) -> int:
    return int(value or "0x0", 16)


def runtime_genesis_text(canonical_text: str) -> str:
    """Return a Besu 25.7-compatible genesis for a non-validator full node.

    Besu 25.7 applies QBFT block-time transitions to historical blocks when a
    time-based hard fork is enabled.  That prevents a new node from syncing an
    existing chain whose earlier blocks used the original, shorter period.
    Keep the canonical genesis unchanged for identity/hash verification, but
    omit only timing changes from the local runtime copy.  A lower historical
    minimum still accepts the network's slower post-transition blocks.
    """
    genesis = json.loads(canonical_text)
    transitions = genesis.get("config", {}).get("transitions", {})
    qbft_transitions = transitions.get("qbft")
    if isinstance(qbft_transitions, list):
        retained = []
        for transition in qbft_transitions:
            if not isinstance(transition, dict):
                retained.append(transition)
                continue
            cleaned = dict(transition)
            cleaned.pop("blockperiodseconds", None)
            cleaned.pop("emptyblockperiodseconds", None)
            cleaned.pop("xemptyblockperiodseconds", None)
            if set(cleaned) != {"block"}:
                retained.append(cleaned)
        if retained:
            transitions["qbft"] = retained
        else:
            transitions.pop("qbft", None)
        if not transitions:
            genesis.get("config", {}).pop("transitions", None)
    return json.dumps(genesis, indent=2) + "\n"


def apply_configuration(configuration) -> None:
    genesis_text = configuration["genesis_text"]
    expected = configuration["genesis_sha256"].lower()
    actual = hashlib.sha256(genesis_text.encode("utf-8")).hexdigest()
    if actual != expected:
        raise RuntimeError(f"Canonical genesis hash mismatch: expected {expected}, received {actual}.")
    genesis_path = CONFIG_DIR / "genesis.json"
    if genesis_path.exists():
        local = hashlib.sha256(genesis_path.read_bytes()).hexdigest()
        if local != expected:
            raise RuntimeError("Local genesis differs from the approved network. Refusing to overwrite it.")
    else:
        atomic_write(genesis_path, genesis_text)
    atomic_write(CONFIG_DIR / "genesis-runtime.json", runtime_genesis_text(genesis_text))
    enodes = sorted(set(configuration.get("nodes_allowlist", [])))
    toml = "nodes-allowlist=[\n" + "".join(f'  {json.dumps(enode)},\n' for enode in enodes) + "]\naccounts-allowlist=[]\n"
    atomic_write(CONFIG_DIR / "permissions_config.toml", toml)
    atomic_write(CONFIG_DIR / "network-configuration.json", json.dumps(configuration, indent=2, sort_keys=True) + "\n")
    try:
        rpc("perm_reloadPermissionsFromFile")
        for enode in configuration.get("bootnodes", []):
            rpc("admin_addPeer", [enode])
    except (OSError, RuntimeError, urllib.error.URLError):
        # Besu may still be starting. The persisted configuration is used at startup.
        pass


def apply_validator_votes(configuration) -> None:
    for vote in configuration.get("validator_votes", []):
        candidate = vote.get("candidate_address")
        if isinstance(candidate, str) and candidate.startswith("0x"):
            rpc("qbft_proposeValidatorVote", [candidate, bool(vote.get("add"))])


def collect_health(configuration, enrollment_status):
    local_block = hex_int(rpc("eth_blockNumber"))
    syncing = rpc("eth_syncing")
    peer_count = hex_int(rpc("net_peerCount"))
    peers = rpc("admin_peers") or []
    peer_enodes = [peer.get("enode") for peer in peers if peer.get("enode")]
    if isinstance(syncing, dict):
        current = hex_int(syncing.get("currentBlock"))
        highest = max(current, hex_int(syncing.get("highestBlock")))
        percentage = 100 if highest == 0 else round((current / highest) * 100, 2)
        state = "SYNCING"
        network_block = highest
    else:
        percentage = 100
        network_block = local_block
        state = "ONLINE" if peer_count > 0 else "DEGRADED"
    try:
        node_info = rpc("admin_nodeInfo") or {}
        validators = [value.lower() for value in (rpc("qbft_getValidatorsByBlockNumber", ["latest"]) or [])]
        role = "VALIDATOR" if enrollment_status.get("is_validator") else "FULL_NODE"
        enode = node_info.get("enode", "")
    except (RuntimeError, urllib.error.URLError):
        validators, role, enode = [], "VALIDATOR" if enrollment_status.get("is_validator") else "FULL_NODE", ""
    node_document = {
        "node_name": os.getenv("NODE_NAME", "ChainControl Node"),
        "node_uuid": NODE_UUID,
        "role": role,
        "status": state,
        "local_block": local_block,
        "network_latest_block": network_block,
        "sync_percentage": percentage,
        "peer_count": peer_count,
        "enode": enode,
        "validator_count": len(validators),
        "network_name": configuration.get("network_name", "ChainControl Network"),
    }
    atomic_write(CONFIG_DIR / "node-config.json", json.dumps(node_document, indent=2) + "\n")
    return {
        "latest_block": local_block,
        "network_latest_block": network_block,
        "peer_count": peer_count,
        "sync_state": state,
        "sync_percentage": percentage,
        "software_version": NODE_VERSION,
        "peer_enodes": peer_enodes,
    }


def main() -> None:
    last_revision = None
    while True:
        try:
            enrollment_status = api(f"/api/v1/network/enrollment/status/{NODE_UUID}/")
            configuration = api(f"/api/v1/network/nodes/{NODE_UUID}/configuration/")
            revision = configuration.get("permissioning_revision")
            if revision != last_revision:
                apply_configuration(configuration)
                last_revision = revision
            apply_validator_votes(configuration)
            health = collect_health(configuration, enrollment_status)
            api(f"/api/v1/network/nodes/{NODE_UUID}/heartbeat/", method="POST", payload=health)
            print(f"heartbeat accepted: block={health['latest_block']} peers={health['peer_count']} state={health['sync_state']}", flush=True)
        except (OSError, KeyError, ValueError, RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"control-plane unavailable: {exc}; Besu continues independently", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
