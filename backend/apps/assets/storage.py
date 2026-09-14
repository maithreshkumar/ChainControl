import base64
import hashlib
import json
import os
from io import BytesIO

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from django.conf import settings
from minio import Minio

from apps.common.errors import DomainError


def _master_key() -> bytes:
    try:
        key = base64.b64decode(settings.ASSET_MASTER_KEY_BASE64, validate=True)
    except Exception as exc:
        raise DomainError("STORAGE_KEY_INVALID", "Asset master key is invalid.", status_code=503) from exc
    if len(key) != 32:
        raise DomainError("STORAGE_KEY_INVALID", "Asset master key must decode to exactly 32 bytes.", status_code=503)
    return key


def _client() -> Minio:
    if not settings.MINIO_ACCESS_KEY or not settings.MINIO_SECRET_KEY:
        raise DomainError("STORAGE_UNAVAILABLE", "Object storage credentials are not configured.", status_code=503)
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def store_encrypted(*, asset_id, version: int, plaintext: bytes, mime_type: str, metadata: dict) -> dict:
    aad = f"chaincontrol:{asset_id}:v{version}".encode()
    data_key = AESGCM.generate_key(bit_length=256)
    content_nonce = os.urandom(12)
    ciphertext = AESGCM(data_key).encrypt(content_nonce, plaintext, aad)
    wrap_nonce = os.urandom(12)
    wrapped_key = AESGCM(_master_key()).encrypt(wrap_nonce, data_key, aad)
    object_key = f"assets/{asset_id}/versions/{version}.enc"
    client = _client()
    try:
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)
        client.put_object(settings.MINIO_BUCKET, object_key, BytesIO(ciphertext), length=len(ciphertext), content_type="application/octet-stream")
    except Exception as exc:
        raise DomainError("STORAGE_UNAVAILABLE", "Encrypted object could not be stored.", status_code=503) from exc
    return {
        "content_hash": hashlib.sha256(plaintext).hexdigest(),
        "metadata_hash": hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "object_key": object_key,
        "content_nonce": base64.b64encode(content_nonce).decode(),
        "wrapped_key": base64.b64encode(wrapped_key).decode(),
        "wrap_nonce": base64.b64encode(wrap_nonce).decode(),
        "size": len(plaintext),
        "mime_type": mime_type,
    }


def retrieve_and_verify(version) -> bytes:
    aad = f"chaincontrol:{version.asset_id}:v{version.version}".encode()
    try:
        response = _client().get_object(settings.MINIO_BUCKET, version.object_key)
        ciphertext = response.read()
        response.close()
        response.release_conn()
        data_key = AESGCM(_master_key()).decrypt(base64.b64decode(version.wrap_nonce), base64.b64decode(version.wrapped_key), aad)
        plaintext = AESGCM(data_key).decrypt(base64.b64decode(version.content_nonce), ciphertext, aad)
    except DomainError:
        raise
    except InvalidTag as exc:
        raise DomainError("INTEGRITY_MISMATCH", "Encrypted asset authentication failed.", status_code=409) from exc
    except Exception as exc:
        raise DomainError("STORAGE_OBJECT_MISSING", "Encrypted object could not be retrieved or authenticated.", status_code=503) from exc
    if hashlib.sha256(plaintext).hexdigest() != version.content_hash:
        raise DomainError("INTEGRITY_MISMATCH", "Asset content does not match its registered hash.", status_code=409)
    return plaintext
