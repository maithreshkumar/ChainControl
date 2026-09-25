import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Department, Permission, Role, User, UserRole
from apps.audit.models import AuditEvent
from apps.common.errors import DomainError
from apps.inventory.models import CatalogItem, CatalogVariant, InventoryCategory, InventoryLocation, InventoryMovement, InventoryRequest, InventoryStock
from apps.inventory.services import issue_request, receive_stock, reserve_request, return_request


pytestmark = pytest.mark.django_db


def grant(user, role_code, *permissions, scope=None):
    role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code.title()})
    for code in permissions:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={"description": code})
        role.permissions.add(permission)
    UserRole.objects.create(user=user, role=role, scope_department=scope, granted_by=user)


@pytest.fixture
def inventory_data():
    department = Department.objects.create(code="ENG", name="Engineering")
    category = InventoryCategory.objects.create(code="HW", name="Hardware", kind=InventoryCategory.Kind.HARDWARE)
    item = CatalogItem.objects.create(
        catalog_code="SCREW",
        name="Machine Screw",
        asset_type=CatalogItem.AssetType.STOCK_ITEM,
        category=category,
    )
    variant = CatalogVariant.objects.create(
        item=item,
        sku="SCR-M3-10-PH-SS",
        name="M3 x 10 mm Phillips Stainless Steel",
        attributes={"diameter": "M3", "length": "10mm", "head": "Phillips", "material": "Stainless Steel"},
    )
    location = InventoryLocation.objects.create(code="WH-A", name="Warehouse A", department=department)
    stock = InventoryStock.objects.create(variant=variant, location=location)
    return department, category, item, variant, location, stock


def test_stock_movement_request_issue_and_return_are_balanced_and_audited(inventory_data):
    department, _, _, variant, _, stock = inventory_data
    admin = User.objects.create_user(username="inventory-admin", email="inventory-admin@example.test", password="StrongPassword123!", department=department)
    employee = User.objects.create_user(username="employee", email="employee@example.test", password="StrongPassword123!", department=department)

    receive_stock(stock_id=stock.id, quantity=1000, actor=admin, reason="Opening balance")
    stock.refresh_from_db()
    assert stock.quantity_available == 1000

    request = InventoryRequest.objects.create(requested_by=employee, variant=variant, stock=stock, department=department, quantity=10)
    reserve_request(request_id=request.id, actor=admin, notes="Approved")
    stock.refresh_from_db()
    request.refresh_from_db()
    assert request.status == InventoryRequest.Status.RESERVED
    assert stock.quantity_on_hand == 1000
    assert stock.quantity_reserved == 10
    assert stock.quantity_available == 990

    issue_request(request_id=request.id, actor=admin, reason="Issued at stores")
    stock.refresh_from_db()
    request.refresh_from_db()
    assert request.status == InventoryRequest.Status.ISSUED
    assert (stock.quantity_on_hand, stock.quantity_reserved, stock.quantity_issued, stock.quantity_available) == (990, 0, 10, 990)

    return_request(request_id=request.id, actor=admin, reason="Returned unused")
    stock.refresh_from_db()
    request.refresh_from_db()
    assert request.status == InventoryRequest.Status.RETURNED
    assert (stock.quantity_on_hand, stock.quantity_reserved, stock.quantity_issued, stock.quantity_available) == (1000, 0, 0, 1000)
    assert InventoryMovement.objects.count() == 4
    assert AuditEvent.objects.filter(action__startswith="inventory.").count() == 4


def test_reservations_cannot_oversell_inventory(inventory_data):
    department, _, _, variant, _, stock = inventory_data
    manager = User.objects.create_user(username="manager", email="manager@example.test", password="StrongPassword123!", department=department)
    alice = User.objects.create_user(username="alice", email="alice@example.test", password="StrongPassword123!", department=department)
    bob = User.objects.create_user(username="bob", email="bob@example.test", password="StrongPassword123!", department=department)
    receive_stock(stock_id=stock.id, quantity=10, actor=manager)
    first = InventoryRequest.objects.create(requested_by=alice, variant=variant, stock=stock, department=department, quantity=7)
    second = InventoryRequest.objects.create(requested_by=bob, variant=variant, stock=stock, department=department, quantity=5)

    reserve_request(request_id=first.id, actor=manager)
    with pytest.raises(DomainError) as exc:
        reserve_request(request_id=second.id, actor=manager)
    assert exc.value.code == "INVENTORY_STOCK_INSUFFICIENT"
    stock.refresh_from_db()
    second.refresh_from_db()
    assert stock.quantity_available == 3
    assert second.status == InventoryRequest.Status.PENDING_APPROVAL


def test_employee_can_request_but_cannot_modify_stock(inventory_data):
    department, _, _, _, _, stock = inventory_data
    employee = User.objects.create_user(username="requester", email="requester@example.test", password="StrongPassword123!", department=department)
    grant(employee, Role.Code.USER, "inventory.view", "inventory.request")
    client = APIClient()
    client.force_authenticate(employee)

    created = client.post("/api/v1/inventory/requests/", {"stock": str(stock.id), "quantity": 2, "reason": "Project work"}, format="json")
    assert created.status_code == 201
    assert created.data["status"] == InventoryRequest.Status.PENDING_APPROVAL

    denied = client.post(f"/api/v1/inventory/stocks/{stock.id}/receive/", {"quantity": 5}, format="json")
    assert denied.status_code == 403


def test_stock_balances_cannot_bypass_the_movement_service(inventory_data):
    _, _, _, _, _, stock = inventory_data
    admin = User.objects.create_user(username="stock-admin", email="stock-admin@example.test", password="StrongPassword123!")
    grant(admin, Role.Code.ADMIN, "inventory.view", "inventory.stock.manage")
    client = APIClient()
    client.force_authenticate(admin)

    response = client.patch(f"/api/v1/inventory/stocks/{stock.id}/", {"quantity_on_hand": 50}, format="json")

    assert response.status_code == 400
    stock.refresh_from_db()
    assert stock.quantity_on_hand == 0
    assert InventoryMovement.objects.count() == 0


def test_manager_scope_prevents_cross_department_approval(inventory_data):
    department, _, _, variant, _, stock = inventory_data
    other = Department.objects.create(code="OPS", name="Operations")
    manager = User.objects.create_user(username="eng-manager", email="eng-manager@example.test", password="StrongPassword123!", department=department)
    requester = User.objects.create_user(username="ops-user", email="ops-user@example.test", password="StrongPassword123!", department=other)
    grant(manager, Role.Code.MANAGER, "inventory.view", "inventory.view_all", "inventory.request.approve", scope=department)
    request = InventoryRequest.objects.create(requested_by=requester, variant=variant, stock=stock, department=other, quantity=1)
    client = APIClient()
    client.force_authenticate(manager)

    response = client.post(f"/api/v1/inventory/requests/{request.id}/approve/", {}, format="json")
    assert response.status_code == 404


def test_admin_can_create_dynamic_catalogue_and_variant():
    admin = User.objects.create_user(username="catalog-admin", email="catalog-admin@example.test", password="StrongPassword123!")
    grant(admin, Role.Code.ADMIN, "inventory.view", "inventory.catalog.manage")
    client = APIClient()
    client.force_authenticate(admin)

    category = client.post("/api/v1/inventory/categories/", {"code": "CONNECTOR", "name": "Connectors", "kind": "HARDWARE"}, format="json")
    assert category.status_code == 201
    item = client.post(
        "/api/v1/inventory/catalog/",
        {"catalog_code": "AUDIO-JACK", "name": "Audio Jack", "asset_type": "STOCK_ITEM", "category": str(category.data["id"]), "unit": "each"},
        format="json",
    )
    assert item.status_code == 201
    variant = client.post(
        "/api/v1/inventory/variants/",
        {"item": str(item.data["id"]), "sku": "JACK-3.5-F", "name": "3.5 mm Female", "attributes": {"diameter": "3.5mm", "type": "female"}},
        format="json",
    )
    assert variant.status_code == 201
    assert CatalogVariant.objects.get().attributes["diameter"] == "3.5mm"
