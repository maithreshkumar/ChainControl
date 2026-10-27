import ipaddress
import re
from urllib.parse import urlsplit

from eth_utils import keccak
from rest_framework import serializers


ENODE_PATTERN = re.compile(r"^enode://(?P<key>[0-9a-fA-F]{128})@(?P<host>\[[0-9a-fA-F:]+\]|[^:/?#]+):(?P<port>[0-9]{1,5})(?:\?discport=[0-9]{1,5})?$")
ADDRESS_PATTERN = re.compile(r"^0x[0-9a-fA-F]{40}$")


def normalize_public_key(value):
    key = str(value).strip().removeprefix("0x").lower()
    if not re.fullmatch(r"[0-9a-f]{128}", key):
        raise serializers.ValidationError("A Besu node public key must contain exactly 128 hexadecimal characters.")
    return key


def address_from_public_key(public_key):
    return "0x" + keccak(bytes.fromhex(normalize_public_key(public_key)))[-20:].hex()


def normalize_address(value):
    address = str(value).strip().lower()
    if not ADDRESS_PATTERN.fullmatch(address):
        raise serializers.ValidationError("A node address must be a 20-byte hexadecimal Ethereum address.")
    return address


def parse_enode(value):
    enode = str(value).strip()
    match = ENODE_PATTERN.fullmatch(enode)
    if not match:
        raise serializers.ValidationError("The enode must include a 128-hex public key, IP address, and valid P2P port.")
    host = match.group("host").strip("[]")
    try:
        normalized_host = str(ipaddress.ip_address(host))
    except ValueError as exc:
        raise serializers.ValidationError("The enode host must be a valid private or overlay IP address.") from exc
    port = int(match.group("port"))
    if port < 1 or port > 65535:
        raise serializers.ValidationError("The enode P2P port is invalid.")
    key = match.group("key").lower()
    rendered_host = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    normalized = f"enode://{key}@{rendered_host}:{port}"
    return normalized, key, normalized_host, port


def validate_private_overlay_ip(value):
    try:
        address = ipaddress.ip_address(str(value))
    except ValueError as exc:
        raise serializers.ValidationError("A valid overlay IP address is required.") from exc
    if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local or address.is_global:
        raise serializers.ValidationError("The node address must be a private or carrier-grade overlay address, not a public, loopback, link-local, multicast, or unspecified address.")
    return str(address)


def ensure_safe_rpc_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"}:
        raise ValueError("Managed Besu RPC URLs must be plain HTTP(S) origins without credentials or paths.")
    return value.rstrip("/")
