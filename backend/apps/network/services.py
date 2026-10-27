import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record_audit

from .models import BlockchainNode, EnrollmentToken, NetworkConfiguration, NodeCredential, NodePeerSnapshot, ValidatorGovernanceOperation
from .validation import ensure_safe_rpc_url


class NetworkAdmissionError(Exception):
    pass


class BesuRpcError(NetworkAdmissionError):
    pass


class BesuRpcClient:
    def __init__(self, url, timeout=8):
        self.url = ensure_safe_rpc_url(url)
        self.timeout = timeout

    def call(self, method, params=None):
        payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}).encode()
        request = Request(self.url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise BesuRpcError(f"Besu RPC {self.url} did not respond to {method}.") from exc
        if result.get("error"):
            message = result["error"].get("message", "Unknown Besu RPC error")
            raise BesuRpcError(f"Besu RPC {self.url} rejected {method}: {message}")
        return result.get("result")


def managed_rpc_clients():
    return [BesuRpcClient(url) for url in settings.BESU_MANAGED_RPC_URLS]


def load_static_enodes():
    path = Path(settings.BESU_STATIC_NODES_PATH)
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NetworkAdmissionError("The canonical static-node file is unavailable or invalid.") from exc
    return list(dict.fromkeys(value for value in rows if isinstance(value, str) and value.startswith("enode://")))


def external_bootnodes():
    """Return host-reachable endpoints for the managed validators when configured."""
    static_enodes = load_static_enodes()
    host = settings.BESU_EXTERNAL_P2P_HOST
    if not host:
        return static_enodes
    base_port = settings.BESU_EXTERNAL_P2P_BASE_PORT
    endpoints = []
    for offset, enode in enumerate(static_enodes):
        identity, separator, _internal_endpoint = enode.partition("@")
        if separator:
            endpoints.append(f"{identity}@{host}:{base_port + offset}")
    return endpoints


def distributable_node_allowlist():
    """Allow canonical identities at both Docker-internal and overlay endpoints."""
    return list(dict.fromkeys(admitted_enodes() + external_bootnodes()))


def admitted_enodes(*, excluding=None, including=None):
    excluded_id = excluding.pk if excluding else None
    statuses = [
        BlockchainNode.Status.APPROVED,
        BlockchainNode.Status.CONNECTING,
        BlockchainNode.Status.SYNCING,
        BlockchainNode.Status.ONLINE,
        BlockchainNode.Status.DEGRADED,
        BlockchainNode.Status.OFFLINE,
    ]
    query = BlockchainNode.objects.filter(status__in=statuses)
    if excluded_id:
        query = query.exclude(pk=excluded_id)
    enodes = load_static_enodes() + list(query.values_list("enode", flat=True))
    if including:
        enodes.append(including.enode)
    return list(dict.fromkeys(enodes))


def permission_toml(enodes):
    rendered = ",\n  ".join(json.dumps(enode) for enode in enodes)
    return f"nodes-allowlist=[\n  {rendered}\n]\naccounts-allowlist=[]\n"


def persist_permission_file(enodes):
    path = Path(settings.BESU_PERMISSION_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
            temporary.write(permission_toml(enodes))
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise NetworkAdmissionError("The persistent Besu node allowlist could not be written.") from exc


def persist_runtime_static_nodes_file(enodes):
    path = Path(settings.BESU_RUNTIME_STATIC_NODES_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
            json.dump(list(dict.fromkeys(enodes)), temporary)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise NetworkAdmissionError("The persistent Besu static-node file could not be written.") from exc


def propagate_allowlist_change(enode, *, add):
    clients = managed_rpc_clients()
    if not clients:
        raise NetworkAdmissionError("No managed Besu RPC endpoints are configured.")
    changed = []
    method = "perm_addNodesToAllowlist" if add else "perm_removeNodesFromAllowlist"
    for client in clients:
        current = client.call("perm_getNodesAllowlist", []) or []
        contains = enode.lower() in {item.lower() for item in current}
        if contains != add:
            client.call(method, [[enode]])
            current = client.call("perm_getNodesAllowlist", []) or []
            contains = enode.lower() in {item.lower() for item in current}
        if contains != add:
            raise NetworkAdmissionError(f"Besu permission verification failed at {client.url}.")
        client.call("admin_addPeer" if add else "admin_removePeer", [enode])
        changed.append(client.url)
    return changed


@transaction.atomic
def create_enrollment(validated):
    code = validated.pop("enrollment_code")
    usable_tokens = EnrollmentToken.objects.select_for_update().filter(used_at__isnull=True, expires_at__gt=timezone.now())
    token = next((candidate for candidate in usable_tokens if candidate.matches(code)), None)
    if token is None:
        raise NetworkAdmissionError("The enrollment code is invalid, expired, or already used.")
    try:
        node = BlockchainNode.objects.create(
            **validated,
            owner=token.intended_owner,
            enrollment_token=token,
            node_type=BlockchainNode.NodeType.FULL_NODE,
            status=BlockchainNode.Status.PENDING,
        )
    except IntegrityError as exc:
        raise NetworkAdmissionError("This node UUID, public identity, address, or enode is already registered.") from exc
    secret = secrets.token_urlsafe(36)
    NodeCredential.objects.create(node=node, secret_digest=make_password(secret))
    token.used_at = timezone.now()
    token.save(update_fields=["used_at", "updated_at"])
    record_audit(
        action="NODE_ENROLLMENT_REQUESTED",
        object_type="BlockchainNode",
        object_id=node.id,
        actor=token.intended_owner,
        details={"node_uuid": str(node.node_uuid), "node_name": node.node_name, "requested_validator": node.requested_validator},
    )
    return node, secret


def network_configuration():
    configuration, _ = NetworkConfiguration.objects.get_or_create(
        pk=1,
        defaults={"network_name": settings.NETWORK_NAME, "chain_id": settings.CHAIN_ID},
    )
    return configuration


@transaction.atomic
def register_canonical_genesis(*, actor=None):
    path = Path(settings.NETWORK_GENESIS_PATH)
    if not path.exists():
        raise NetworkAdmissionError("The existing generated Besu genesis is not available.")
    raw = path.read_bytes()
    try:
        genesis = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NetworkAdmissionError("The existing generated Besu genesis is invalid JSON.") from exc
    chain_id = int(genesis.get("config", {}).get("chainId", 0))
    if chain_id != settings.CHAIN_ID:
        raise NetworkAdmissionError(f"Genesis chain ID {chain_id} does not match configured chain ID {settings.CHAIN_ID}.")
    configuration = network_configuration()
    digest = hashlib.sha256(raw).hexdigest()
    if configuration.genesis_hash and configuration.genesis_hash != digest:
        raise NetworkAdmissionError("The generated genesis differs from the canonical genesis already registered. Refusing replacement.")
    configuration.network_name = settings.NETWORK_NAME
    configuration.chain_id = chain_id
    configuration.genesis_hash = digest
    configuration.genesis_json = genesis
    configuration.genesis_text = raw.decode("utf-8")
    configuration.updated_by = actor
    configuration.save()
    return configuration


def approve_node(node, actor):
    candidate = BlockchainNode.objects.get(pk=node.pk)
    if candidate.status != BlockchainNode.Status.PENDING:
        raise NetworkAdmissionError("Only pending nodes can be approved.")
    configuration = network_configuration()
    if not configuration.genesis_hash or not configuration.genesis_json or not configuration.genesis_text:
        raise NetworkAdmissionError("Register the exact existing genesis before approving a node.")
    try:
        changed = propagate_allowlist_change(candidate.enode, add=True)
        admitted = admitted_enodes(including=candidate)
        persist_permission_file(admitted)
        persist_runtime_static_nodes_file(admitted)
    except NetworkAdmissionError as exc:
        BlockchainNode.objects.filter(pk=candidate.pk).update(configuration_error=str(exc))
        record_audit(action="NODE_APPROVED", object_type="BlockchainNode", object_id=candidate.id, actor=actor, outcome="FAILED", details={"reason": str(exc)})
        raise
    with transaction.atomic():
        locked = BlockchainNode.objects.select_for_update().get(pk=candidate.pk)
        if locked.status != BlockchainNode.Status.PENDING:
            raise NetworkAdmissionError("The node changed state while permissioning was being propagated.")
        now = timezone.now()
        locked.status = BlockchainNode.Status.APPROVED
        locked.approved_at = now
        locked.approved_by = actor
        locked.configuration_error = ""
        locked.save(update_fields=["status", "approved_at", "approved_by", "configuration_error", "updated_at"])
        configuration = NetworkConfiguration.objects.select_for_update().get(pk=configuration.pk)
        configuration.permissioning_revision += 1
        configuration.updated_by = actor
        configuration.save(update_fields=["permissioning_revision", "updated_by", "updated_at"])
    record_audit(
        action="NODE_APPROVED",
        object_type="BlockchainNode",
        object_id=locked.id,
        actor=actor,
        details={"node_uuid": str(locked.node_uuid), "propagated_to": changed, "revision": configuration.permissioning_revision},
    )
    return locked


@transaction.atomic
def reject_node(node, actor, reason=""):
    locked = BlockchainNode.objects.select_for_update().get(pk=node.pk)
    if locked.status != BlockchainNode.Status.PENDING:
        raise NetworkAdmissionError("Only pending nodes can be rejected.")
    locked.status = BlockchainNode.Status.REJECTED
    locked.rejected_by = actor
    locked.rejection_reason = reason.strip()
    locked.save(update_fields=["status", "rejected_by", "rejection_reason", "updated_at"])
    record_audit(action="NODE_REJECTED", object_type="BlockchainNode", object_id=locked.id, actor=actor, details={"reason": locked.rejection_reason})
    return locked


def revoke_node(node, actor, reason=""):
    candidate = BlockchainNode.objects.get(pk=node.pk)
    if not candidate.is_admitted:
        raise NetworkAdmissionError("Only admitted nodes can be revoked.")
    try:
        changed = propagate_allowlist_change(candidate.enode, add=False)
        admitted = admitted_enodes(excluding=candidate)
        persist_permission_file(admitted)
        persist_runtime_static_nodes_file(admitted)
    except NetworkAdmissionError as exc:
        BlockchainNode.objects.filter(pk=candidate.pk).update(status=BlockchainNode.Status.DEGRADED, configuration_error=str(exc))
        record_audit(action="NODE_REVOKED", object_type="BlockchainNode", object_id=candidate.id, actor=actor, outcome="FAILED", details={"reason": str(exc)})
        raise
    with transaction.atomic():
        locked = BlockchainNode.objects.select_for_update().get(pk=candidate.pk)
        locked.status = BlockchainNode.Status.REVOKED
        locked.revoked_by = actor
        locked.revocation_reason = reason.strip()
        locked.configuration_error = ""
        locked.save(update_fields=["status", "revoked_by", "revocation_reason", "configuration_error", "updated_at"])
        configuration = NetworkConfiguration.objects.select_for_update().get(pk=network_configuration().pk)
        configuration.permissioning_revision += 1
        configuration.updated_by = actor
        configuration.save(update_fields=["permissioning_revision", "updated_by", "updated_at"])
    record_audit(action="NODE_REVOKED", object_type="BlockchainNode", object_id=locked.id, actor=actor, details={"reason": locked.revocation_reason, "propagated_to": changed, "revision": configuration.permissioning_revision})
    return locked


def bootstrap_configuration_for(node):
    if not node.is_admitted:
        raise NetworkAdmissionError("This node has not been approved for the network.")
    configuration = network_configuration()
    if not configuration.genesis_hash or not configuration.genesis_json:
        raise NetworkAdmissionError("The canonical genesis is not available.")
    bootnodes = [enode for enode in external_bootnodes() if enode.lower() != node.enode.lower()]
    validator_votes = []
    if node.is_validator:
        validator_votes = [
            {
                "operation_id": str(operation.id),
                "candidate_address": operation.candidate_address,
                "add": operation.action == ValidatorGovernanceOperation.Action.ADD,
            }
            for operation in ValidatorGovernanceOperation.objects.filter(status=ValidatorGovernanceOperation.Status.IN_PROGRESS)
        ]
    return {
        "network_name": configuration.network_name,
        "chain_id": configuration.chain_id,
        "genesis_sha256": configuration.genesis_hash,
        "genesis": configuration.genesis_json,
        "genesis_text": configuration.genesis_text,
        "permissioning_revision": configuration.permissioning_revision,
        "nodes_allowlist": distributable_node_allowlist(),
        "bootnodes": bootnodes,
        "validator_votes": validator_votes,
    }


def current_validator_set():
    errors = []
    for client in managed_rpc_clients():
        try:
            validators = client.call("qbft_getValidatorsByBlockNumber", ["latest"]) or []
            return [value.lower() for value in validators]
        except BesuRpcError as exc:
            errors.append(str(exc))
    raise BesuRpcError("No managed Besu endpoint returned the current validator set: " + "; ".join(errors))


def refresh_managed_node_health():
    """Project actual private managed-RPC health into registered bootstrap nodes."""
    observations = []
    now = timezone.now()
    for client in managed_rpc_clients():
        try:
            info = client.call("admin_nodeInfo") or {}
            public_key = str(info.get("id", "")).removeprefix("0x").lower()
            node = BlockchainNode.objects.filter(node_public_key=public_key).first()
            if node is None:
                continue
            latest = int(client.call("eth_blockNumber"), 16)
            peer_count = int(client.call("net_peerCount"), 16)
            syncing = client.call("eth_syncing")
            if isinstance(syncing, dict):
                current = int(syncing.get("currentBlock", "0x0"), 16)
                highest = max(current, int(syncing.get("highestBlock", "0x0"), 16))
                percentage = 100 if highest == 0 else round(current / highest * 100, 2)
                state = BlockchainNode.Status.SYNCING
            else:
                highest = latest
                percentage = 100
                state = BlockchainNode.Status.ONLINE
            peers = client.call("admin_peers") or []
            peer_enodes = [peer.get("enode") for peer in peers if isinstance(peer, dict) and peer.get("enode")]
            observations.append((node, latest, highest, peer_count, percentage, state, peer_enodes))
        except (BesuRpcError, TypeError, ValueError):
            continue
    network_height = max((row[2] for row in observations), default=0)
    for node, latest, highest, peer_count, percentage, state, peer_enodes in observations:
        previous_status = node.status
        node.latest_block = latest
        node.network_latest_block = max(network_height, highest)
        node.peer_count = peer_count
        node.sync_percentage = percentage
        node.sync_state = state
        node.status = state
        node.last_seen = now
        node.save(update_fields=["latest_block", "network_latest_block", "peer_count", "sync_percentage", "sync_state", "status", "last_seen", "updated_at"])
        NodePeerSnapshot.objects.filter(reporter=node).exclude(peer_enode__in=peer_enodes).delete()
        for enode in peer_enodes:
            NodePeerSnapshot.objects.update_or_create(reporter=node, peer_enode=enode, defaults={"observed_at": now})
        if state == BlockchainNode.Status.ONLINE and previous_status != BlockchainNode.Status.ONLINE:
            record_audit(action="NODE_SYNCED", object_type="BlockchainNode", object_id=node.id, details={"latest_block": latest, "managed_rpc": True})
    return len(observations)


@transaction.atomic
def initiate_validator_change(node, actor, *, add):
    locked = BlockchainNode.objects.select_for_update().get(pk=node.pk)
    if locked.status not in {BlockchainNode.Status.ONLINE, BlockchainNode.Status.APPROVED}:
        raise NetworkAdmissionError("The node must be approved and online before validator governance.")
    if add and (locked.sync_percentage is None or locked.sync_percentage < 100):
        raise NetworkAdmissionError("The node must be fully synchronized before promotion.")
    before = current_validator_set()
    candidate = locked.node_address.lower()
    if add and candidate in before:
        raise NetworkAdmissionError("The node is already in the active validator set.")
    if not add and candidate not in before:
        raise NetworkAdmissionError("The node is not in the active validator set.")
    if not add and len(before) <= 1:
        raise NetworkAdmissionError("The final active validator cannot be removed.")
    operation = ValidatorGovernanceOperation.objects.create(
        node=locked,
        action=ValidatorGovernanceOperation.Action.ADD if add else ValidatorGovernanceOperation.Action.REMOVE,
        status=ValidatorGovernanceOperation.Status.IN_PROGRESS,
        candidate_address=candidate,
        requested_by=actor,
        validator_set_before=before,
    )
    votes = []
    for client in managed_rpc_clients():
        try:
            accepted = client.call("qbft_proposeValidatorVote", [candidate, add])
            votes.append({"rpc": client.url, "accepted": bool(accepted)})
        except BesuRpcError as exc:
            votes.append({"rpc": client.url, "accepted": False, "error": str(exc)})
    operation.votes = votes
    operation.save(update_fields=["votes", "updated_at"])
    action = "VALIDATOR_PROMOTION_REQUESTED" if add else "VALIDATOR_REMOVAL_REQUESTED"
    record_audit(action=action, object_type="BlockchainNode", object_id=locked.id, actor=actor, details={"candidate": candidate, "votes": votes})
    return refresh_validator_operation(operation)


@transaction.atomic
def refresh_validator_operation(operation):
    locked = ValidatorGovernanceOperation.objects.select_for_update().select_related("node").get(pk=operation.pk)
    if locked.status == ValidatorGovernanceOperation.Status.COMPLETED:
        return locked
    try:
        validators = current_validator_set()
    except BesuRpcError as exc:
        locked.error_message = str(exc)
        locked.save(update_fields=["error_message", "updated_at"])
        return locked
    target_present = locked.candidate_address.lower() in validators
    complete = target_present if locked.action == ValidatorGovernanceOperation.Action.ADD else not target_present
    locked.validator_set_after = validators
    if complete:
        locked.status = ValidatorGovernanceOperation.Status.COMPLETED
        locked.completed_at = timezone.now()
        locked.error_message = ""
        node = locked.node
        node.is_validator = locked.action == ValidatorGovernanceOperation.Action.ADD
        node.node_type = BlockchainNode.NodeType.VALIDATOR if node.is_validator else BlockchainNode.NodeType.FULL_NODE
        node.save(update_fields=["is_validator", "node_type", "updated_at"])
        action = "VALIDATOR_ADDED" if node.is_validator else "VALIDATOR_REMOVED"
        record_audit(action=action, object_type="BlockchainNode", object_id=node.id, actor=locked.requested_by, details={"validator_set": validators})
    locked.save(update_fields=["validator_set_after", "status", "completed_at", "error_message", "updated_at"])
    return locked
