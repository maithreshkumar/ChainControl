import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.mark.django_db
def test_valid_login_succeeds_and_wrong_password_is_rejected():
    User.objects.create_user(username="alice", email="alice@example.test", password="a-very-long-password")
    client = APIClient()

    valid = client.post("/api/v1/auth/token/", {"username": "alice", "password": "a-very-long-password"}, format="json")
    invalid = client.post("/api/v1/auth/token/", {"username": "alice", "password": "wrong-password"}, format="json")

    assert valid.status_code == 200
    assert "access" in valid.data and "refresh" in valid.data
    assert invalid.status_code == 401
    assert invalid.data["error"]["code"] == "REQUEST_INVALID"

