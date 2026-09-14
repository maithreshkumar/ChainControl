import pytest

from apps.accounts.models import Department, Permission, Role, User, UserRole


@pytest.mark.django_db
def test_django_superuser_has_no_implicit_platform_authority():
    user = User.objects.create_superuser(username="operator", email="operator@example.test", password="very-long-password")
    assert user.is_superuser
    assert not user.has_platform_permission("asset.mint")


@pytest.mark.django_db
def test_department_scoped_permission_isolated():
    radar = Department.objects.create(code="RADAR", name="Radar")
    naval = Department.objects.create(code="NAVAL", name="Naval")
    manager = User.objects.create_user(username="manager", email="manager@example.test", password="very-long-password", department=radar)
    permission = Permission.objects.create(code="transfer.approve", description="Approve transfers")
    role = Role.objects.create(code=Role.Code.MANAGER, name="Manager")
    role.permissions.add(permission)
    UserRole.objects.create(user=manager, role=role, scope_department=radar, granted_by=manager)

    assert manager.has_platform_permission("transfer.approve", department_id=radar.id)
    assert not manager.has_platform_permission("transfer.approve", department_id=naval.id)

