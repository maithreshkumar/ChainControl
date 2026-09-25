from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.common.models import UUIDTimeStampedModel


class InventoryCategory(UUIDTimeStampedModel):
    class Kind(models.TextChoices):
        HARDWARE = "HARDWARE", "Hardware"
        SOFTWARE = "SOFTWARE", "Software / digital"

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=Kind)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]
        verbose_name_plural = "Inventory categories"

    def __str__(self):
        return f"{self.code} · {self.name}"


class InventorySubcategory(UUIDTimeStampedModel):
    category = models.ForeignKey(InventoryCategory, on_delete=models.PROTECT, related_name="subcategories")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["category", "code"], name="unique_inventory_subcategory_code"),
        ]

    def __str__(self):
        return f"{self.category.code} / {self.name}"


class CatalogItem(UUIDTimeStampedModel):
    class AssetType(models.TextChoices):
        STOCK_ITEM = "STOCK_ITEM", "Stock / consumable item"
        UNIQUE_PHYSICAL_ASSET = "UNIQUE_PHYSICAL_ASSET", "Unique physical asset"
        DIGITAL_ASSET = "DIGITAL_ASSET", "Digital asset"
        SOFTWARE_LICENSE = "SOFTWARE_LICENSE", "Software license"

    catalog_code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    asset_type = models.CharField(max_length=32, choices=AssetType)
    category = models.ForeignKey(InventoryCategory, on_delete=models.PROTECT, related_name="items")
    subcategory = models.ForeignKey("InventorySubcategory", null=True, blank=True, on_delete=models.PROTECT, related_name="items")
    unit = models.CharField(max_length=32, default="each")
    requestable = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="created_catalog_items")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="updated_catalog_items")

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["asset_type", "active"]), models.Index(fields=["category", "active"])]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.subcategory_id and self.subcategory.category_id != self.category_id:
            raise ValidationError({"subcategory": "Subcategory must belong to the selected category."})

    def __str__(self):
        return f"{self.catalog_code} · {self.name}"


class CatalogVariant(UUIDTimeStampedModel):
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="variants")
    sku = models.CharField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=180)
    attributes = models.JSONField(default=dict, blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)
    model_number = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["item__name", "name"]
        indexes = [models.Index(fields=["item", "active"])]

    def __str__(self):
        return f"{self.sku} · {self.name}"


class InventoryLocation(UUIDTimeStampedModel):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    department = models.ForeignKey("accounts.Department", null=True, blank=True, on_delete=models.PROTECT, related_name="inventory_locations")
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} · {self.name}"


class InventoryStock(UUIDTimeStampedModel):
    variant = models.ForeignKey(CatalogVariant, on_delete=models.PROTECT, related_name="stocks")
    location = models.ForeignKey(InventoryLocation, on_delete=models.PROTECT, related_name="stocks")
    quantity_on_hand = models.PositiveBigIntegerField(default=0)
    quantity_reserved = models.PositiveBigIntegerField(default=0)
    quantity_issued = models.PositiveBigIntegerField(default=0)
    reorder_threshold = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ["variant__item__name", "variant__name", "location__name"]
        constraints = [
            models.UniqueConstraint(fields=["variant", "location"], name="unique_variant_location_stock"),
            models.CheckConstraint(condition=Q(quantity_reserved__lte=F("quantity_on_hand")), name="reserved_not_above_on_hand"),
        ]
        indexes = [models.Index(fields=["location", "variant"])]

    @property
    def quantity_available(self):
        return self.quantity_on_hand - self.quantity_reserved

    @property
    def low_stock(self):
        return self.quantity_available <= self.reorder_threshold

    def __str__(self):
        return f"{self.variant.sku} @ {self.location.code}"


class InventoryRequest(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        RESERVED = "RESERVED", "Reserved"
        ISSUED = "ISSUED", "Issued"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        RETURNED = "RETURNED", "Returned"

    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inventory_requests")
    variant = models.ForeignKey(CatalogVariant, on_delete=models.PROTECT, related_name="requests")
    stock = models.ForeignKey("InventoryStock", on_delete=models.PROTECT, related_name="requests")
    department = models.ForeignKey("accounts.Department", null=True, on_delete=models.PROTECT, related_name="inventory_requests")
    quantity = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=24, choices=Status, default=Status.PENDING_APPROVAL)
    reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_inventory_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["department", "status"]),
            models.Index(fields=["requested_by", "status"]),
        ]

    def __str__(self):
        return f"{self.requested_by.username} · {self.variant.sku} · {self.status}"


class InventoryReservation(UUIDTimeStampedModel):
    request = models.OneToOneField(InventoryRequest, on_delete=models.PROTECT, related_name="reservation")
    stock = models.ForeignKey(InventoryStock, on_delete=models.PROTECT, related_name="reservations")
    quantity = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    active = models.BooleanField(default=True)
    reserved_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Reservation {self.request_id}"


class InventoryMovement(UUIDTimeStampedModel):
    class Type(models.TextChoices):
        STOCK_IN = "STOCK_IN", "Stock in"
        STOCK_OUT = "STOCK_OUT", "Stock out"
        RESERVE = "RESERVE", "Reserve"
        RELEASE = "RELEASE", "Release"
        ISSUE = "ISSUE", "Issue"
        RETURN = "RETURN", "Return"
        TRANSFER = "TRANSFER", "Transfer"
        ADJUST = "ADJUST", "Adjust"

    stock = models.ForeignKey(InventoryStock, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=16, choices=Type)
    quantity = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    previous_on_hand = models.PositiveBigIntegerField()
    new_on_hand = models.PositiveBigIntegerField()
    previous_reserved = models.PositiveBigIntegerField()
    new_reserved = models.PositiveBigIntegerField()
    previous_issued = models.PositiveBigIntegerField()
    new_issued = models.PositiveBigIntegerField()
    request = models.ForeignKey(InventoryRequest, null=True, blank=True, on_delete=models.PROTECT, related_name="movements")
    related_stock = models.ForeignKey(InventoryStock, null=True, blank=True, on_delete=models.PROTECT, related_name="related_movements")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="inventory_movements")
    issued_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="issued_inventory_movements")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approved_inventory_movements")
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["movement_type", "created_at"]), models.Index(fields=["stock", "created_at"])]

    def __str__(self):
        return f"{self.movement_type} · {self.stock} · {self.quantity}"
