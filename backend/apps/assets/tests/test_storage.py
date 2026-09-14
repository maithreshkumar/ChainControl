import base64
from types import SimpleNamespace

import pytest
from django.test import override_settings

from apps.assets import storage
from apps.common.errors import DomainError


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def close(self):
        pass

    def release_conn(self):
        pass


class FakeMinio:
    def __init__(self):
        self.objects = {}

    def bucket_exists(self, bucket):
        return True

    def make_bucket(self, bucket):
        pass

    def put_object(self, bucket, key, source, length, content_type):
        self.objects[(bucket, key)] = source.read(length)

    def get_object(self, bucket, key):
        return FakeResponse(self.objects[(bucket, key)])


@override_settings(
    ASSET_MASTER_KEY_BASE64=base64.b64encode(b"k" * 32).decode(),
    MINIO_BUCKET="test-assets",
)
def test_encrypted_object_round_trip_and_tamper_detection(monkeypatch):
    fake = FakeMinio()
    monkeypatch.setattr(storage, "_client", lambda: fake)
    asset_id = "78ef5944-7d88-46db-a0ee-790c34caa5c8"
    values = storage.store_encrypted(
        asset_id=asset_id,
        version=1,
        plaintext=b"classified-content",
        mime_type="application/octet-stream",
        metadata={"name": "example"},
    )
    assert b"classified-content" not in fake.objects[("test-assets", values["object_key"])]
    version = SimpleNamespace(asset_id=asset_id, version=1, **values)
    assert storage.retrieve_and_verify(version) == b"classified-content"

    key = ("test-assets", values["object_key"])
    ciphertext = bytearray(fake.objects[key])
    ciphertext[-1] ^= 1
    fake.objects[key] = bytes(ciphertext)
    with pytest.raises(DomainError) as tampered:
        storage.retrieve_and_verify(version)
    assert tampered.value.code == "INTEGRITY_MISMATCH"

