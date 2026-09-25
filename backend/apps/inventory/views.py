from django.db.models import F, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import record_audit
from apps.common.errors import DomainError
from apps.common.permissions import HasPermissionCode

from .models import CatalogItem, CatalogVariant, InventoryCategory, InventoryLocation, InventoryMovement, InventoryRequest, InventoryStock, InventorySubcategory
from .serializers import (
    AdjustmentSerializer,
    CatalogItemSerializer,
    CatalogVariantSerializer,
    InventoryCategorySerializer,
    InventoryLocationSerializer,
    InventoryMovementSerializer,
    InventoryRequestSerializer,
    InventoryStockSerializer,
    InventorySubcategorySerializer,
    QuantityActionSerializer,
    ReviewSerializer,
    StockTransferSerializer,
)
from .services import adjust_stock, issue_request, receive_stock, release_request, reserve_request, return_request, transfer_stock


class PermissionMappedViewSet(viewsets.ModelViewSet):
    read_permission = "inventory.view"
    write_permission = "inventory.catalog.manage"

    def get_permissions(self):
        self.permission_code = self.read_permission if self.action in {"list", "retrieve"} else self.write_permission
        return [HasPermissionCode()]


class InventoryCategoryViewSet(PermissionMappedViewSet):
    queryset = InventoryCategory.objects.all()
    serializer_class = InventoryCategorySerializer


class InventorySubcategoryViewSet(PermissionMappedViewSet):
    queryset = InventorySubcategory.objects.select_related("category").all()
    serializer_class = InventorySubcategorySerializer


class CatalogItemViewSet(PermissionMappedViewSet):
    serializer_class = CatalogItemSerializer

    def get_queryset(self):
        queryset = CatalogItem.objects.select_related("category", "subcategory").all()
        asset_type = self.request.query_params.get("asset_type")
        category = self.request.query_params.get("category")
        search = self.request.query_params.get("search")
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)
        if category:
            queryset = queryset.filter(category_id=category)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(catalog_code__icontains=search) | Q(description__icontains=search))
        if not self.request.user.has_platform_permission("inventory.catalog.manage"):
            queryset = queryset.filter(active=True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class CatalogVariantViewSet(PermissionMappedViewSet):
    serializer_class = CatalogVariantSerializer

    def get_queryset(self):
        queryset = CatalogVariant.objects.select_related("item", "item__category").all()
        item = self.request.query_params.get("item")
        search = self.request.query_params.get("search")
        if item:
            queryset = queryset.filter(item_id=item)
        if search:
            queryset = queryset.filter(Q(sku__icontains=search) | Q(name__icontains=search))
        if not self.request.user.has_platform_permission("inventory.catalog.manage"):
            queryset = queryset.filter(active=True, item__active=True)
        return queryset


class InventoryLocationViewSet(PermissionMappedViewSet):
    queryset = InventoryLocation.objects.select_related("department").all()
    serializer_class = InventoryLocationSerializer


class InventoryStockViewSet(PermissionMappedViewSet):
    serializer_class = InventoryStockSerializer
    write_permission = "inventory.stock.manage"
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = InventoryStock.objects.select_related("variant", "variant__item", "variant__item__category", "location", "location__department")
        search = self.request.query_params.get("search")
        asset_type = self.request.query_params.get("asset_type")
        category = self.request.query_params.get("category")
        available = self.request.query_params.get("available")
        if search:
            queryset = queryset.filter(Q(variant__sku__icontains=search) | Q(variant__name__icontains=search) | Q(variant__item__name__icontains=search))
        if asset_type:
            queryset = queryset.filter(variant__item__asset_type=asset_type)
        if category:
            queryset = queryset.filter(variant__item__category_id=category)
        if available in {"1", "true", "yes"}:
            queryset = queryset.filter(quantity_on_hand__gt=F("quantity_reserved"))
        return queryset.filter(variant__active=True, variant__item__active=True, location__active=True)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        self.permission_code = "inventory.stock.manage"
        serializer = QuantityActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stock = receive_stock(stock_id=pk, actor=request.user, **serializer.validated_data)
        return Response(self.get_serializer(stock).data)

    @action(detail=True, methods=["post"])
    def adjust(self, request, pk=None):
        self.permission_code = "inventory.stock.manage"
        serializer = AdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stock = adjust_stock(stock_id=pk, actor=request.user, **serializer.validated_data)
        return Response(self.get_serializer(stock).data)

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        self.permission_code = "inventory.stock.manage"
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source, destination = transfer_stock(
            source_id=pk,
            destination_id=serializer.validated_data["destination_stock"].id,
            quantity=serializer.validated_data["quantity"],
            actor=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response({"source": self.get_serializer(source).data, "destination": self.get_serializer(destination).data})


class InventoryRequestViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryRequestSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        mapping = {
            "create": "inventory.request",
            "approve": "inventory.request.approve",
            "reject": "inventory.request.approve",
            "issue": "inventory.issue",
            "return_item": "inventory.issue",
            "cancel": "inventory.request",
        }
        self.permission_code = mapping.get(self.action, "inventory.view")
        return [HasPermissionCode()]

    def get_queryset(self):
        queryset = InventoryRequest.objects.select_related("requested_by", "variant", "variant__item", "stock", "stock__location", "reviewed_by")
        user = self.request.user
        if user.has_platform_permission("inventory.view_all"):
            assignments = user.role_assignments.filter(active=True, role__permissions__code="inventory.view_all")
            if not assignments.filter(scope_department__isnull=True).exists():
                queryset = queryset.filter(department_id__in=assignments.exclude(scope_department__isnull=True).values("scope_department_id"))
            return queryset
        return queryset.filter(requested_by=user)

    def perform_create(self, serializer):
        stock = serializer.validated_data["stock"]
        item = stock.variant.item
        if not item.requestable or not item.active or not stock.variant.active:
            raise DomainError("INVENTORY_NOT_REQUESTABLE", "This item is not currently requestable.", status_code=409)
        inventory_request = serializer.save(
            requested_by=self.request.user,
            variant=stock.variant,
            department=self.request.user.department,
            status=InventoryRequest.Status.PENDING_APPROVAL if item.requires_approval else InventoryRequest.Status.REQUESTED,
        )
        record_audit(
            action="inventory.request.created",
            object_type="InventoryRequest",
            object_id=inventory_request.id,
            actor=self.request.user,
            details={"sku": stock.variant.sku, "quantity": inventory_request.quantity},
        )

    def _require_scope(self, request, inventory_request, permission):
        if inventory_request.department_id and not request.user.has_platform_permission(permission, department_id=inventory_request.department_id):
            raise DomainError("ROLE_NOT_AUTHORIZED", "This request is outside your department scope.", status_code=403)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        inventory_request = self.get_object()
        self._require_scope(request, inventory_request, "inventory.request.approve")
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inventory_request = reserve_request(request_id=inventory_request.id, actor=request.user, notes=serializer.validated_data.get("notes", ""))
        return Response(self.get_serializer(inventory_request).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        inventory_request = self.get_object()
        self._require_scope(request, inventory_request, "inventory.request.approve")
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inventory_request = release_request(request_id=inventory_request.id, actor=request.user, final_status=InventoryRequest.Status.REJECTED, reason=serializer.validated_data.get("notes", ""))
        return Response(self.get_serializer(inventory_request).data)

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        inventory_request = self.get_object()
        self._require_scope(request, inventory_request, "inventory.issue")
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inventory_request = issue_request(request_id=inventory_request.id, actor=request.user, reason=serializer.validated_data.get("notes", ""))
        return Response(self.get_serializer(inventory_request).data)

    @action(detail=True, methods=["post"], url_path="return")
    def return_item(self, request, pk=None):
        inventory_request = self.get_object()
        self._require_scope(request, inventory_request, "inventory.issue")
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inventory_request = return_request(request_id=inventory_request.id, actor=request.user, reason=serializer.validated_data.get("notes", ""))
        return Response(self.get_serializer(inventory_request).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        inventory_request = self.get_object()
        if inventory_request.requested_by_id != request.user.id:
            raise DomainError("INVENTORY_REQUEST_NOT_OWNED", "Only the requester can cancel this request.", status_code=403)
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inventory_request = release_request(request_id=inventory_request.id, actor=request.user, final_status=InventoryRequest.Status.CANCELLED, reason=serializer.validated_data.get("notes", ""))
        return Response(self.get_serializer(inventory_request).data)


class InventoryMovementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryMovementSerializer
    permission_classes = [HasPermissionCode]
    permission_code = "inventory.audit"

    def get_queryset(self):
        queryset = InventoryMovement.objects.select_related("stock", "stock__variant", "stock__location", "actor", "issued_to", "approved_by")
        user = self.request.user
        if user.has_platform_permission("inventory.view_all"):
            assignments = user.role_assignments.filter(active=True, role__permissions__code="inventory.view_all")
            if not assignments.filter(scope_department__isnull=True).exists():
                queryset = queryset.filter(stock__location__department_id__in=assignments.exclude(scope_department__isnull=True).values("scope_department_id"))
            return queryset
        return queryset.filter(Q(request__requested_by=user) | Q(issued_to=user)).distinct()
