from rest_framework import serializers

from .models import (
    CatalogItem,
    CatalogVariant,
    InventoryCategory,
    InventoryLocation,
    InventoryMovement,
    InventoryRequest,
    InventoryStock,
    InventorySubcategory,
)


class InventoryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryCategory
        fields = "__all__"


class InventorySubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = InventorySubcategory
        fields = "__all__"


class CatalogItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.name", allow_null=True, read_only=True)

    class Meta:
        model = CatalogItem
        fields = "__all__"
        read_only_fields = ("created_by", "updated_by")

    def validate(self, attrs):
        category = attrs.get("category", getattr(self.instance, "category", None))
        subcategory = attrs.get("subcategory", getattr(self.instance, "subcategory", None))
        if subcategory and category and subcategory.category_id != category.id:
            raise serializers.ValidationError({"subcategory": "Subcategory must belong to the selected category."})
        return attrs


class CatalogVariantSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    asset_type = serializers.CharField(source="item.asset_type", read_only=True)

    class Meta:
        model = CatalogVariant
        fields = "__all__"


class InventoryLocationSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source="department.code", allow_null=True, read_only=True)

    class Meta:
        model = InventoryLocation
        fields = "__all__"


class InventoryStockSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="variant.sku", read_only=True)
    item_name = serializers.CharField(source="variant.item.name", read_only=True)
    variant_name = serializers.CharField(source="variant.name", read_only=True)
    asset_type = serializers.CharField(source="variant.item.asset_type", read_only=True)
    category = serializers.CharField(source="variant.item.category.name", read_only=True)
    location_code = serializers.CharField(source="location.code", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    department_code = serializers.CharField(source="location.department.code", allow_null=True, read_only=True)
    quantity_available = serializers.IntegerField(read_only=True)
    low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryStock
        fields = "__all__"

    def validate(self, attrs):
        protected = {"quantity_on_hand", "quantity_reserved", "quantity_issued"}
        supplied = protected.intersection(self.initial_data)
        if self.instance is not None and supplied:
            raise serializers.ValidationError("Stock balances can only change through receive, adjust, transfer, issue, and return actions.")
        if self.instance is None and any(int(self.initial_data.get(field, 0)) != 0 for field in supplied):
            raise serializers.ValidationError("New stock records must start at zero; use the receive action to add an opening balance.")
        return attrs


class InventoryRequestSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    sku = serializers.CharField(source="variant.sku", read_only=True)
    item_name = serializers.CharField(source="variant.item.name", read_only=True)
    location_code = serializers.CharField(source="stock.location.code", read_only=True)
    reviewed_by_username = serializers.CharField(source="reviewed_by.username", allow_null=True, read_only=True)

    class Meta:
        model = InventoryRequest
        fields = "__all__"
        read_only_fields = (
            "requested_by",
            "variant",
            "department",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
        )

    def validate(self, attrs):
        stock = attrs.get("stock")
        if stock and (not stock.variant.active or not stock.variant.item.active or not stock.variant.item.requestable):
            raise serializers.ValidationError({"stock": "This catalogue item is not currently requestable."})
        return attrs


class InventoryMovementSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="stock.variant.sku", read_only=True)
    location_code = serializers.CharField(source="stock.location.code", read_only=True)
    actor_username = serializers.CharField(source="actor.username", allow_null=True, read_only=True)

    class Meta:
        model = InventoryMovement
        fields = "__all__"


class QuantityActionSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class AdjustmentSerializer(serializers.Serializer):
    new_on_hand = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(min_length=3, max_length=2000)


class StockTransferSerializer(QuantityActionSerializer):
    destination_stock = serializers.PrimaryKeyRelatedField(queryset=InventoryStock.objects.all())


class ReviewSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
