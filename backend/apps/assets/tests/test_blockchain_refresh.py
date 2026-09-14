from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Permission, Role, User, UserRole


@pytest.mark.django_db
@patch("apps.blockchain.tasks.track_pending_transactions.delay")
def test_asset_user_can_queue_blockchain_refresh(refresh_delay):
    user = User.objects.create_user(
        username="asset-user",
        email="asset-user@example.test",
        password="very-long-password",
    )
    permission = Permission.objects.create(code="asset.view", description="View assets")
    role = Role.objects.create(code=Role.Code.USER, name="User")
    role.permissions.add(permission)
    UserRole.objects.create(user=user, role=role, granted_by=user)
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(reverse("asset-refresh-blockchain"))

    assert response.status_code == 202
    assert response.data["status"] == "QUEUED"
    refresh_delay.assert_called_once_with()
