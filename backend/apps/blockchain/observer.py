from datetime import datetime, timezone as datetime_timezone

from django.db.models import Q
from eth_utils import event_signature_to_log_topic
from web3._utils.events import get_event_data

from apps.assets.models import Asset, TransferRequest
from apps.common.errors import DomainError
from apps.identities.models import DecentralizedIdentity

from .client import get_web3
from .models import BlockchainTransaction, ContractDeployment


def json_value(value):
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if hasattr(value, "hex") and not isinstance(value, (str, int)):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    return value


def normalize_hash(value):
    if not value:
        return ""
    text = value.hex() if hasattr(value, "hex") else str(value)
    return text if text.startswith("0x") else f"0x{text}"


def hash_variants(value):
    normalized = normalize_hash(value)
    return normalized, normalized[2:]


def deployment_map(web3):
    deployments = ContractDeployment.objects.filter(active=True)
    return {
        deployment.address.lower(): (deployment, web3.eth.contract(address=web3.to_checksum_address(deployment.address), abi=deployment.abi))
        for deployment in deployments
    }


def decode_transaction(web3, tx, deployments=None):
    deployments = deployments or deployment_map(web3)
    target = tx.get("to")
    if not target or target.lower() not in deployments or not tx.get("input") or tx["input"] in {"0x", b""}:
        return {"contract": None, "function": None, "parameters": {}}
    deployment, contract = deployments[target.lower()]
    try:
        function, parameters = contract.decode_function_input(tx["input"])
        return {"contract": deployment.name, "function": function.fn_name, "parameters": json_value(parameters)}
    except Exception:
        return {"contract": deployment.name, "function": None, "parameters": {}}


def decode_events(web3, receipt, deployments=None):
    deployments = deployments or deployment_map(web3)
    decoded = []
    for log in receipt.get("logs", []):
        entry = deployments.get(log["address"].lower())
        if entry is None or not log.get("topics"):
            continue
        deployment, _ = entry
        for event_abi in (item for item in deployment.abi if item.get("type") == "event"):
            signature = f"{event_abi['name']}({','.join(parameter['type'] for parameter in event_abi.get('inputs', []))})"
            if event_signature_to_log_topic(signature) != log["topics"][0]:
                continue
            try:
                event = get_event_data(web3.codec, event_abi, log)
                decoded.append({"contract": deployment.name, "event": event_abi["name"], "parameters": json_value(dict(event["args"])), "log_index": log["logIndex"]})
            except Exception:
                pass
            break
    return decoded


def business_transaction(tx_hash):
    prefixed, bare = hash_variants(tx_hash)
    return BlockchainTransaction.objects.filter(Q(tx_hash__iexact=prefixed) | Q(tx_hash__iexact=bare)).first()


def business_context(row):
    if row is None:
        return None
    context = {
        "operation": row.operation,
        "actor_did": row.actor_did,
        "status": row.status,
        "correlation_id": str(row.correlation_id) if row.correlation_id else None,
        "related_object_type": row.related_object_type,
        "related_object_id": row.related_object_id,
    }
    if row.related_object_type == "Asset":
        asset = Asset.objects.filter(id=row.related_object_id).select_related("owner_projection", "department").first()
        if asset:
            context["asset"] = {"id": str(asset.id), "name": asset.name, "token_id": asset.token_id, "state": asset.state, "owner_did": asset.owner_projection.did if asset.owner_projection else None}
    elif row.related_object_type == "TransferRequest":
        transfer = TransferRequest.objects.filter(id=row.related_object_id).select_related("asset", "sender", "recipient").first()
        if transfer:
            context["transfer"] = {"id": str(transfer.id), "asset_id": str(transfer.asset_id), "asset_name": transfer.asset.name, "token_id": transfer.asset.token_id, "sender_did": transfer.sender.did, "recipient_did": transfer.recipient.did, "state": transfer.state}
    elif row.related_object_type == "DecentralizedIdentity":
        identity = DecentralizedIdentity.objects.filter(id=row.related_object_id).select_related("user", "user__department").first()
        if identity:
            context["identity"] = {"id": str(identity.id), "username": identity.user.username, "did": identity.did, "department": identity.user.department.code if identity.user.department else None, "state": identity.state}
    return context


def transaction_summary(web3, tx, deployments=None):
    decoded = decode_transaction(web3, tx, deployments)
    row = business_transaction(tx["hash"])
    return {
        "hash": normalize_hash(tx["hash"]),
        "index": tx.get("transactionIndex"),
        "from": tx.get("from"),
        "to": tx.get("to"),
        "operation": row.operation if row else decoded["function"] or "Contract transaction",
        "contract": decoded["contract"],
        "function": decoded["function"],
    }


def block_data(identifier, *, transaction_preview=8, include_all=False, web3=None):
    web3 = web3 or get_web3()
    try:
        block = web3.eth.get_block(identifier, full_transactions=True)
    except Exception as exc:
        raise DomainError("BLOCK_NOT_FOUND", "Blockchain block was not found.", status_code=404) from exc
    deployments = deployment_map(web3)
    transactions = [transaction_summary(web3, tx, deployments) for tx in block["transactions"]]
    shown = transactions if include_all else transactions[:transaction_preview]
    return {
        "number": block["number"],
        "hash": normalize_hash(block["hash"]),
        "parent_hash": normalize_hash(block["parentHash"]),
        "timestamp": datetime.fromtimestamp(block["timestamp"], tz=datetime_timezone.utc).isoformat(),
        "miner": block.get("miner"),
        "gas_limit": block.get("gasLimit"),
        "gas_used": block.get("gasUsed"),
        "size": block.get("size"),
        "transaction_count": len(transactions),
        "transactions": shown,
        "transactions_truncated": len(shown) < len(transactions),
        "finalized": block["number"] < web3.eth.block_number,
    }


def transaction_data(tx_hash):
    web3 = get_web3()
    try:
        tx = web3.eth.get_transaction(tx_hash)
        receipt = web3.eth.get_transaction_receipt(tx_hash)
        block = web3.eth.get_block(tx["blockNumber"])
    except Exception as exc:
        raise DomainError("TRANSACTION_NOT_FOUND", "Blockchain transaction was not found.", status_code=404) from exc
    deployments = deployment_map(web3)
    decoded = decode_transaction(web3, tx, deployments)
    row = business_transaction(tx_hash)
    return {
        "hash": normalize_hash(tx["hash"]),
        "block_number": tx["blockNumber"],
        "block_hash": normalize_hash(tx["blockHash"]),
        "transaction_index": tx["transactionIndex"],
        "timestamp": datetime.fromtimestamp(block["timestamp"], tz=datetime_timezone.utc).isoformat(),
        "from": tx["from"],
        "to": tx.get("to"),
        "nonce": tx["nonce"],
        "value": tx["value"],
        "gas": tx["gas"],
        "gas_price": tx.get("gasPrice"),
        "gas_used": receipt["gasUsed"],
        "status": "SUCCESS" if receipt["status"] == 1 else "REVERTED",
        "contract_address": receipt.get("contractAddress"),
        "decoded": decoded,
        "events": decode_events(web3, receipt, deployments),
        "business": business_context(row),
        "raw_input": tx["input"].hex() if hasattr(tx["input"], "hex") else str(tx["input"]),
    }


def validator_status(index, url):
    web3 = get_web3(url)
    block_height = web3.eth.block_number
    peer_response = web3.provider.make_request("net_peerCount", [])
    validator_response = web3.provider.make_request("qbft_getValidatorsByBlockNumber", ["latest"])
    peers = int(peer_response.get("result", "0x0"), 16) if peer_response.get("result") else None
    validators = validator_response.get("result") or []
    return {"validator": index, "rpc": url, "healthy": True, "block_height": block_height, "peer_count": peers, "validator_count": len(validators), "validator_addresses": validators}
