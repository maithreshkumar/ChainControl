from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit
from apps.common.errors import DomainError

from .models import InventoryMovement, InventoryRequest, InventoryReservation, InventoryStock


def _snapshot(stock):
    return stock.quantity_on_hand, stock.quantity_reserved, stock.quantity_issued


def _movement(*, stock, movement_type, quantity, previous, actor, request=None, related_stock=None, issued_to=None, approved_by=None, reason=""):
    movement = InventoryMovement.objects.create(
        stock=stock,
        movement_type=movement_type,
        quantity=quantity,
        previous_on_hand=previous[0],
        new_on_hand=stock.quantity_on_hand,
        previous_reserved=previous[1],
        new_reserved=stock.quantity_reserved,
        previous_issued=previous[2],
        new_issued=stock.quantity_issued,
        request=request,
        related_stock=related_stock,
        actor=actor,
        issued_to=issued_to,
        approved_by=approved_by,
        reason=reason,
    )
    record_audit(
        action=f"inventory.{movement_type.lower()}",
        object_type="InventoryStock",
        object_id=stock.id,
        actor=actor,
        details={
            "movement_id": str(movement.id),
            "sku": stock.variant.sku,
            "quantity": quantity,
            "previous_on_hand": previous[0],
            "new_on_hand": stock.quantity_on_hand,
            "previous_reserved": previous[1],
            "new_reserved": stock.quantity_reserved,
            "request_id": str(request.id) if request else None,
        },
    )
    return movement


@transaction.atomic
def receive_stock(*, stock_id, quantity, actor, reason=""):
    if quantity <= 0:
        raise DomainError("INVENTORY_QUANTITY_INVALID", "Quantity must be greater than zero.")
    stock = InventoryStock.objects.select_for_update().select_related("variant").get(id=stock_id)
    previous = _snapshot(stock)
    stock.quantity_on_hand += quantity
    stock.save(update_fields=["quantity_on_hand", "updated_at"])
    _movement(stock=stock, movement_type=InventoryMovement.Type.STOCK_IN, quantity=quantity, previous=previous, actor=actor, reason=reason)
    return stock


@transaction.atomic
def adjust_stock(*, stock_id, new_on_hand, actor, reason):
    if new_on_hand < 0:
        raise DomainError("INVENTORY_QUANTITY_INVALID", "Adjusted quantity cannot be negative.")
    stock = InventoryStock.objects.select_for_update().select_related("variant").get(id=stock_id)
    if new_on_hand < stock.quantity_reserved:
        raise DomainError("INVENTORY_RESERVED_CONFLICT", "Adjusted quantity cannot be lower than the reserved quantity.", status_code=409)
    previous = _snapshot(stock)
    difference = abs(new_on_hand - stock.quantity_on_hand)
    if difference == 0:
        raise DomainError("INVENTORY_NO_CHANGE", "Adjusted quantity is unchanged.", status_code=409)
    stock.quantity_on_hand = new_on_hand
    stock.save(update_fields=["quantity_on_hand", "updated_at"])
    _movement(stock=stock, movement_type=InventoryMovement.Type.ADJUST, quantity=difference, previous=previous, actor=actor, reason=reason)
    return stock


@transaction.atomic
def reserve_request(*, request_id, actor, notes=""):
    inventory_request = InventoryRequest.objects.select_for_update().select_related("stock__variant", "requested_by").get(id=request_id)
    if inventory_request.status not in {InventoryRequest.Status.REQUESTED, InventoryRequest.Status.PENDING_APPROVAL}:
        raise DomainError("INVENTORY_REQUEST_STATE_INVALID", "Only a pending request can be approved.", status_code=409)
    stock = InventoryStock.objects.select_for_update().select_related("variant").get(id=inventory_request.stock_id)
    if stock.quantity_available < inventory_request.quantity:
        raise DomainError("INVENTORY_STOCK_INSUFFICIENT", "Insufficient available stock for this request.", status_code=409)
    previous = _snapshot(stock)
    stock.quantity_reserved += inventory_request.quantity
    stock.save(update_fields=["quantity_reserved", "updated_at"])
    now = timezone.now()
    InventoryReservation.objects.create(
        request=inventory_request,
        stock=stock,
        quantity=inventory_request.quantity,
        active=True,
        reserved_at=now,
    )
    inventory_request.status = InventoryRequest.Status.RESERVED
    inventory_request.reviewed_by = actor
    inventory_request.reviewed_at = now
    inventory_request.review_notes = notes
    inventory_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes", "updated_at"])
    _movement(
        stock=stock,
        movement_type=InventoryMovement.Type.RESERVE,
        quantity=inventory_request.quantity,
        previous=previous,
        actor=actor,
        request=inventory_request,
        approved_by=actor,
        reason=notes,
    )
    return inventory_request


@transaction.atomic
def issue_request(*, request_id, actor, reason=""):
    inventory_request = InventoryRequest.objects.select_for_update().select_related("requested_by").get(id=request_id)
    if inventory_request.status != InventoryRequest.Status.RESERVED:
        raise DomainError("INVENTORY_REQUEST_STATE_INVALID", "Only a reserved request can be issued.", status_code=409)
    reservation = InventoryReservation.objects.select_for_update().get(request=inventory_request, active=True)
    stock = InventoryStock.objects.select_for_update().select_related("variant").get(id=reservation.stock_id)
    if stock.quantity_on_hand < reservation.quantity or stock.quantity_reserved < reservation.quantity:
        raise DomainError("INVENTORY_STOCK_INCONSISTENT", "Reserved stock is no longer available.", status_code=409)
    previous = _snapshot(stock)
    stock.quantity_on_hand -= reservation.quantity
    stock.quantity_reserved -= reservation.quantity
    stock.quantity_issued += reservation.quantity
    stock.save(update_fields=["quantity_on_hand", "quantity_reserved", "quantity_issued", "updated_at"])
    now = timezone.now()
    reservation.active = False
    reservation.issued_at = now
    reservation.save(update_fields=["active", "issued_at", "updated_at"])
    inventory_request.status = InventoryRequest.Status.ISSUED
    inventory_request.save(update_fields=["status", "updated_at"])
    _movement(
        stock=stock,
        movement_type=InventoryMovement.Type.ISSUE,
        quantity=reservation.quantity,
        previous=previous,
        actor=actor,
        request=inventory_request,
        issued_to=inventory_request.requested_by,
        approved_by=inventory_request.reviewed_by,
        reason=reason,
    )
    return inventory_request


@transaction.atomic
def release_request(*, request_id, actor, final_status, reason=""):
    if final_status not in {InventoryRequest.Status.CANCELLED, InventoryRequest.Status.REJECTED}:
        raise DomainError("INVENTORY_REQUEST_STATE_INVALID", "Invalid release status.")
    inventory_request = InventoryRequest.objects.select_for_update().get(id=request_id)
    if inventory_request.status in {InventoryRequest.Status.REQUESTED, InventoryRequest.Status.PENDING_APPROVAL}:
        inventory_request.status = final_status
        inventory_request.reviewed_by = actor if final_status == InventoryRequest.Status.REJECTED else inventory_request.reviewed_by
        inventory_request.reviewed_at = timezone.now() if final_status == InventoryRequest.Status.REJECTED else inventory_request.reviewed_at
        inventory_request.review_notes = reason
        inventory_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes", "updated_at"])
        record_audit(action=f"inventory.request.{final_status.lower()}", object_type="InventoryRequest", object_id=inventory_request.id, actor=actor, details={"reason": reason})
        return inventory_request
    if inventory_request.status != InventoryRequest.Status.RESERVED:
        raise DomainError("INVENTORY_REQUEST_STATE_INVALID", "This request cannot be released.", status_code=409)
    reservation = InventoryReservation.objects.select_for_update().get(request=inventory_request, active=True)
    stock = InventoryStock.objects.select_for_update().select_related("variant").get(id=reservation.stock_id)
    if stock.quantity_reserved < reservation.quantity:
        raise DomainError("INVENTORY_STOCK_INCONSISTENT", "Reserved stock is inconsistent.", status_code=409)
    previous = _snapshot(stock)
    stock.quantity_reserved -= reservation.quantity
    stock.save(update_fields=["quantity_reserved", "updated_at"])
    reservation.active = False
    reservation.released_at = timezone.now()
    reservation.save(update_fields=["active", "released_at", "updated_at"])
    inventory_request.status = final_status
    inventory_request.review_notes = reason
    inventory_request.save(update_fields=["status", "review_notes", "updated_at"])
    _movement(stock=stock, movement_type=InventoryMovement.Type.RELEASE, quantity=reservation.quantity, previous=previous, actor=actor, request=inventory_request, reason=reason)
    return inventory_request


@transaction.atomic
def return_request(*, request_id, actor, reason=""):
    inventory_request = InventoryRequest.objects.select_for_update().select_related("requested_by").get(id=request_id)
    if inventory_request.status != InventoryRequest.Status.ISSUED:
        raise DomainError("INVENTORY_REQUEST_STATE_INVALID", "Only issued inventory can be returned.", status_code=409)
    stock = InventoryStock.objects.select_for_update().select_related("variant").get(id=inventory_request.stock_id)
    if stock.quantity_issued < inventory_request.quantity:
        raise DomainError("INVENTORY_STOCK_INCONSISTENT", "Issued stock is inconsistent.", status_code=409)
    previous = _snapshot(stock)
    stock.quantity_on_hand += inventory_request.quantity
    stock.quantity_issued -= inventory_request.quantity
    stock.save(update_fields=["quantity_on_hand", "quantity_issued", "updated_at"])
    inventory_request.status = InventoryRequest.Status.RETURNED
    inventory_request.save(update_fields=["status", "updated_at"])
    _movement(stock=stock, movement_type=InventoryMovement.Type.RETURN, quantity=inventory_request.quantity, previous=previous, actor=actor, request=inventory_request, issued_to=inventory_request.requested_by, reason=reason)
    return inventory_request


@transaction.atomic
def transfer_stock(*, source_id, destination_id, quantity, actor, reason=""):
    if source_id == destination_id:
        raise DomainError("INVENTORY_TRANSFER_INVALID", "Source and destination must differ.")
    if quantity <= 0:
        raise DomainError("INVENTORY_QUANTITY_INVALID", "Quantity must be greater than zero.")
    ids = sorted([str(source_id), str(destination_id)])
    locked = {str(stock.id): stock for stock in InventoryStock.objects.select_for_update().select_related("variant").filter(id__in=ids).order_by("id")}
    source = locked.get(str(source_id))
    destination = locked.get(str(destination_id))
    if source is None or destination is None:
        raise DomainError("INVENTORY_STOCK_NOT_FOUND", "Source or destination stock was not found.", status_code=404)
    if source.variant_id != destination.variant_id:
        raise DomainError("INVENTORY_TRANSFER_INVALID", "Stock can only move between locations for the same SKU.")
    if source.quantity_available < quantity:
        raise DomainError("INVENTORY_STOCK_INSUFFICIENT", "Insufficient available stock for this transfer.", status_code=409)
    source_previous = _snapshot(source)
    destination_previous = _snapshot(destination)
    source.quantity_on_hand -= quantity
    destination.quantity_on_hand += quantity
    source.save(update_fields=["quantity_on_hand", "updated_at"])
    destination.save(update_fields=["quantity_on_hand", "updated_at"])
    _movement(stock=source, movement_type=InventoryMovement.Type.TRANSFER, quantity=quantity, previous=source_previous, actor=actor, related_stock=destination, reason=reason)
    _movement(stock=destination, movement_type=InventoryMovement.Type.STOCK_IN, quantity=quantity, previous=destination_previous, actor=actor, related_stock=source, reason=f"Transfer from {source.location.code}: {reason}".strip())
    return source, destination
