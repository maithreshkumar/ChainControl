import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import User
from apps.assets.models import Asset, AssetVersion, IntegrityCheck, TransferRequest
from apps.audit.models import AuditEvent, SecurityAlert
from apps.blockchain.models import BlockchainEvent, BlockchainTransaction, ContractDeployment


@pytest.mark.django_db
def test_blockchain_asset_and_audit_admin_models_are_strictly_read_only():
    administrator = User.objects.create_superuser(
        username="blockchain-viewer",
        email="blockchain-viewer@example.test",
        password="admin-test-password",
    )
    request = RequestFactory().get("/admin/")
    request.user = administrator

    protected_models = (
        BlockchainTransaction,
        BlockchainEvent,
        ContractDeployment,
        Asset,
        AssetVersion,
        IntegrityCheck,
        TransferRequest,
        AuditEvent,
        SecurityAlert,
    )
    for model in protected_models:
        model_admin = admin.site._registry[model]
        assert model_admin.has_view_permission(request)
        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)
        assert model_admin.get_actions(request) == {}


@pytest.mark.django_db
def test_blockchain_change_page_cannot_be_posted_or_deleted(client):
    administrator = User.objects.create_superuser(
        username="blockchain-admin-viewer",
        email="blockchain-admin-viewer@example.test",
        password="admin-test-password",
    )
    deployment = ContractDeployment.objects.create(
        name="AssetRegistry",
        version="1.0.0",
        chain_id=1337,
        address="0x1111111111111111111111111111111111111111",
        abi=[],
        deployment_tx_hash="0x" + "1" * 64,
        deployment_block=1,
        active=True,
    )
    client.force_login(administrator)
    change_url = reverse("admin:blockchain_contractdeployment_change", args=[deployment.pk])

    page = client.get(change_url)
    content = page.content.decode()
    forbidden_change = client.post(change_url, {"name": "Tampered", "_save": "Save"})
    forbidden_add = client.get(reverse("admin:blockchain_contractdeployment_add"))
    forbidden_delete = client.post(reverse("admin:blockchain_contractdeployment_delete", args=[deployment.pk]))

    assert page.status_code == 200
    assert 'name="_save"' not in content
    assert "Delete" not in content
    assert forbidden_change.status_code == 403
    assert forbidden_add.status_code == 403
    assert forbidden_delete.status_code == 403
    deployment.refresh_from_db()
    assert deployment.name == "AssetRegistry"
