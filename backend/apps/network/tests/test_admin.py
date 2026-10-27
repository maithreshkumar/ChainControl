from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.network.models import EnrollmentToken
from apps.network.models import BlockchainNode
from apps.network.tests.test_enrollment import identity


@pytest.mark.django_db
def test_enrollment_token_admin_hides_owner_and_reveals_generated_code_once(client):
    administrator = User.objects.create_superuser(
        username="network-admin",
        email="network-admin@example.test",
        password="admin-test-password",
    )
    client.force_login(administrator)
    add_url = reverse("admin:network_enrollmenttoken_add")

    form_page = client.get(add_url)

    assert form_page.status_code == 200
    assert 'name="intended_owner"' not in form_page.content.decode()

    expires_at = timezone.now() + timedelta(hours=24)
    response = client.post(
        add_url,
        {
            "label": "Local full node test",
            "expires_at_0": expires_at.strftime("%Y-%m-%d"),
            "expires_at_1": expires_at.strftime("%H:%M:%S"),
            "enrollment_code": "",
            "_save": "Save",
        },
    )

    token = EnrollmentToken.objects.get(label="Local full node test")
    reveal_url = reverse("admin:network_enrollmenttoken_reveal", args=[token.pk])
    assert response.status_code == 302
    assert response.url == reveal_url

    reveal = client.get(reveal_url)
    content = reveal.content.decode()
    assert reveal.status_code == 200
    assert "Copy this code now" in content
    assert "JOIN-" in content
    assert "Copy code" in content

    repeated = client.get(reveal_url)
    assert repeated.status_code == 302
    assert repeated.url == reverse("admin:network_enrollmenttoken_changelist")


@pytest.mark.django_db
def test_pending_node_admin_shows_yes_no_decision_and_approves(client, monkeypatch):
    administrator = User.objects.create_superuser(
        username="node-review-admin",
        email="node-review-admin@example.test",
        password="admin-test-password",
    )
    node = BlockchainNode.objects.create(**identity(), status=BlockchainNode.Status.PENDING)
    client.force_login(administrator)
    change_url = reverse("admin:network_blockchainnode_change", args=[node.pk])

    page = client.get(change_url)
    content = page.content.decode()
    assert page.status_code == 200
    assert "Yes — approve node" in content
    assert "No — reject node" in content

    def approve_for_test(selected, actor):
        selected.status = BlockchainNode.Status.APPROVED
        selected.approved_by = actor
        selected.save(update_fields=["status", "approved_by", "updated_at"])
        return selected

    monkeypatch.setattr("apps.network.admin.approve_node", approve_for_test)
    response = client.post(change_url, {"_approve_node": "yes"})

    assert response.status_code == 302
    assert response.url == change_url
    node.refresh_from_db()
    assert node.status == BlockchainNode.Status.APPROVED
