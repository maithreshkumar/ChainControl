import pytest
from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.accounts.models import Invitation, Permission, Profile, Role, User, UserRole


@pytest.mark.django_db
def test_profile_change_page_links_to_its_users_password_reset(client):
    administrator = User.objects.create_superuser(
        username="dashboard-admin",
        email="dashboard-admin@example.test",
        password="admin-test-password",
    )
    person = User.objects.create_user(
        username="profile-user",
        email="profile-user@example.test",
        password="current-test-password",
    )
    profile = Profile.objects.create(user=person, employee_id="EMP-ADMIN-TEST")
    client.force_login(administrator)

    response = client.get(reverse("admin:accounts_profile_change", args=[profile.pk]))

    assert response.status_code == 200
    expected_url = reverse("admin:auth_user_password_change", args=[person.pk])
    assert expected_url in response.content.decode()
    assert "Reset password" in response.content.decode()


@pytest.mark.django_db
def test_profile_password_reset_target_is_available_to_admin(client):
    administrator = User.objects.create_superuser(
        username="password-admin",
        email="password-admin@example.test",
        password="admin-test-password",
    )
    person = User.objects.create_user(
        username="password-user",
        email="password-user@example.test",
        password="current-test-password",
    )
    client.force_login(administrator)

    response = client.get(reverse("admin:auth_user_password_change", args=[person.pk]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_profile_admin_can_change_username_employee_id_and_password(client):
    administrator = User.objects.create_superuser(
        username="profile-editor",
        email="profile-editor@example.test",
        password="admin-test-password",
    )
    person = User.objects.create_user(
        username="old-username",
        email="person@example.test",
        password="current-test-password",
    )
    profile = Profile.objects.create(user=person, employee_id="EMP-OLD")
    client.force_login(administrator)

    page = client.get(reverse("admin:accounts_profile_change", args=[profile.pk]))
    assert page.status_code == 200
    assert 'name="username"' in page.content.decode()
    assert 'name="new_password"' in page.content.decode()

    response = client.post(
        reverse("admin:accounts_profile_change", args=[profile.pk]),
        {
            "username": "new-username",
            "email": "updated-person@example.test",
            "first_name": "Updated",
            "last_name": "Person",
            "department": "",
            "employee_id": "EMP-NEW",
            "clearance": Profile.Clearance.CONFIDENTIAL,
            "new_password": "NewProfilePassword123!",
            "confirm_password": "NewProfilePassword123!",
            "_save": "Save",
        },
    )

    assert response.status_code == 302
    person.refresh_from_db()
    profile.refresh_from_db()
    assert person.username == "new-username"
    assert person.email == "updated-person@example.test"
    assert person.check_password("NewProfilePassword123!")
    assert profile.employee_id == "EMP-NEW"
    assert profile.clearance == Profile.Clearance.CONFIDENTIAL


@pytest.mark.django_db
def test_user_admin_consolidates_invitation_roles_and_permissions(client):
    administrator = User.objects.create_superuser(
        username="people-admin",
        email="people-admin@example.test",
        password="admin-test-password",
    )
    person = User.objects.create_user(
        username="consolidated-user",
        email="consolidated-user@example.test",
        password="current-test-password",
    )
    permission = Permission.objects.create(code="asset.view", description="View assets")
    role = Role.objects.create(code=Role.Code.USER, name="User")
    role.permissions.add(permission)
    UserRole.objects.create(user=person, role=role, granted_by=administrator)
    Invitation.objects.create(
        email=person.email,
        username=person.username,
        employee_id="INVITED-EMP",
        role=role,
        token_digest="a" * 64,
        expires_at=person.date_joined,
        accepted_at=person.date_joined,
        created_by=administrator,
    )
    client.force_login(administrator)

    response = client.get(reverse("admin:accounts_user_change", args=[person.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "people-admin" in content
    assert "asset.view" in content
    assert "Platform roles" in content
    assert 'name="username"' in content
    assert admin.site.is_registered(User)
    assert not admin.site.is_registered(Invitation)
    assert not admin.site.is_registered(Permission)
    assert not admin.site.is_registered(Role)
    assert not admin.site.is_registered(UserRole)


@pytest.mark.django_db
def test_history_button_is_only_visible_when_the_object_has_admin_history(client):
    administrator = User.objects.create_superuser(
        username="history-admin",
        email="history-admin@example.test",
        password="admin-test-password",
    )
    person = User.objects.create_user(
        username="history-person",
        email="history-person@example.test",
        password="current-test-password",
    )
    profile = Profile.objects.create(user=person, employee_id="EMP-HISTORY")
    client.force_login(administrator)
    url = reverse("admin:accounts_profile_change", args=[profile.pk])

    without_history = client.get(url).content.decode()
    assert ">History<" not in without_history

    LogEntry.objects.create(
        user=administrator,
        content_type=ContentType.objects.get_for_model(profile, for_concrete_model=False),
        object_id=str(profile.pk),
        object_repr=str(profile),
        action_flag=CHANGE,
        change_message="Profile reviewed",
    )
    with_history = client.get(url).content.decode()

    assert ">History<" in with_history
