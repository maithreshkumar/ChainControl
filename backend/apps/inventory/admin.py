from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import CatalogItem, CatalogVariant, InventoryCategory, InventoryLocation, InventoryMovement, InventoryRequest, InventoryReservation, InventoryStock, InventorySubcategory


class SubcategoryInline(admin.TabularInline):
    model = InventorySubcategory
    extra = 0


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "active")
    list_filter = ("kind", "active")
    search_fields = ("code", "name")
    inlines = (SubcategoryInline,)


class VariantInline(admin.TabularInline):
    model = CatalogVariant
    extra = 0


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    list_display = ("catalog_code", "name", "asset_type", "category", "requestable", "active")
    list_filter = ("asset_type", "category", "requestable", "active")
    search_fields = ("catalog_code", "name", "description")
    inlines = (VariantInline,)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CatalogVariant)
class CatalogVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "item", "manufacturer", "active")
    list_filter = ("active", "item__asset_type", "item__category")
    search_fields = ("sku", "name", "manufacturer", "model_number")


@admin.register(InventoryLocation)
class InventoryLocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "active")
    list_filter = ("department", "active")
    search_fields = ("code", "name")


@admin.register(InventoryStock)
class InventoryStockAdmin(admin.ModelAdmin):
    list_display = ("variant", "location", "quantity_on_hand", "quantity_reserved", "available", "quantity_issued", "reorder_threshold")
    list_filter = ("location", "variant__item__asset_type", "variant__item__category")
    search_fields = ("variant__sku", "variant__name", "variant__item__name", "location__code")
    readonly_fields = ("quantity_on_hand", "quantity_reserved", "quantity_issued")

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Available")
    def available(self, obj):
        return obj.quantity_available


@admin.register(InventoryRequest)
class InventoryRequestAdmin(ReadOnlyAdmin):
    list_display = ("requested_by", "variant", "quantity", "status", "department", "reviewed_by", "created_at")
    list_filter = ("status", "department", "variant__item__asset_type")
    search_fields = ("requested_by__username", "variant__sku", "variant__name", "reason")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(ReadOnlyAdmin):
    list_display = ("movement_type", "stock", "quantity", "actor", "issued_to", "created_at")
    list_filter = ("movement_type", "stock__location")
    search_fields = ("stock__variant__sku", "actor__username", "issued_to__username", "reason")


@admin.register(InventoryReservation)
class InventoryReservationAdmin(ReadOnlyAdmin):
    list_display = ("request", "stock", "quantity", "active", "reserved_at", "issued_at", "released_at")
    list_filter = ("active",)
