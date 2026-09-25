import hashlib
import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.assets.models import Asset, AssetVersion
from apps.audit.models import AuditEvent


pytestmark = pytest.mark.django_db


def make_version():
    actor = User.objects.create_superuser(username="decrypt-admin", email="decrypt@example.test", password="unused")
    asset = Asset.objects.create(
        name="Encrypted report", kind=Asset.Kind.DIGITAL, asset_type=Asset.AssetType.DIGITAL_ASSET,
        classification=20, created_by=actor,
    )
    plaintext = b"authenticated enterprise asset"
    version = AssetVersion.objects.create(
        asset=asset, version=1, content_hash=hashlib.sha256(plaintext).hexdigest(), metadata_hash="0" * 64,
        object_key=f"assets/{asset.id}/versions/1.enc", content_nonce="nonce", wrap_nonce="nonce",
        wrapped_key="wrapped", size=len(plaintext), mime_type="application/octet-stream",
    )
    return actor, asset, version, plaintext


def test_admin_decrypt_writes_controlled_output_and_audits(monkeypatch, tmp_path):
    actor, asset, version, plaintext = make_version()
    monkeypatch.setattr("apps.assets.management.commands.decrypt_asset.retrieve_and_verify", lambda value: plaintext)
    output = tmp_path / "authorized" / "report.bin"

    call_command("decrypt_asset", str(asset.id), actor=actor.username, reason="Incident review", output=str(output))

    assert output.read_bytes() == plaintext
    event = AuditEvent.objects.get(action="ADMIN_DECRYPT")
    assert event.outcome == "SUCCESS"
    assert event.actor == actor
    assert event.details["reason"] == "Incident review"
    assert event.details["source_object"] == version.object_key
    assert "key" not in event.details


def test_invalid_asset_id_is_rejected_and_audited(tmp_path):
    actor = User.objects.create_superuser(username="decrypt-admin", email="decrypt@example.test", password="unused")
    with pytest.raises(CommandError):
        call_command("decrypt_asset", "not-a-uuid", actor=actor.username, reason="Test", output=str(tmp_path / "out"))
    assert AuditEvent.objects.filter(action="ADMIN_DECRYPT", outcome="FAILED", object_id="not-a-uuid").exists()


def test_decrypt_failure_does_not_leave_plaintext_or_log_keys(monkeypatch, tmp_path):
    actor, asset, _, _ = make_version()
    output = tmp_path / "out.bin"
    monkeypatch.setattr("apps.assets.management.commands.decrypt_asset.retrieve_and_verify", lambda value: (_ for _ in ()).throw(RuntimeError("authentication failed")))
    with pytest.raises(CommandError):
        call_command("decrypt_asset", str(asset.id), actor=actor.username, reason="Test", output=str(output))
    assert not output.exists()
    event = AuditEvent.objects.get(action="ADMIN_DECRYPT")
    assert event.outcome == "FAILED"
    assert "key" not in str(event.details).lower()


def test_cleanup_is_only_performed_when_explicit(monkeypatch, tmp_path):
    actor, asset, _, plaintext = make_version()
    monkeypatch.setattr("apps.assets.management.commands.decrypt_asset.retrieve_and_verify", lambda value: plaintext)
    output = tmp_path / "temporary.bin"
    call_command("decrypt_asset", str(asset.id), actor=actor.username, reason="One-time review", output=str(output), cleanup=True)
    assert not output.exists()
    assert AuditEvent.objects.get(action="ADMIN_DECRYPT").details["result"] == "DECRYPTED_AND_CLEANED"
