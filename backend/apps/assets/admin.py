from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import Asset, AssetVersion, IntegrityCheck, TransferRequest


@admin.register(Asset)
class AssetAdmin(ReadOnlyAdmin):
    list_display = ("name", "kind", "state", "token_id", "owner_projection", "department")
    search_fields = ("name", "serial_number", "custody_identifier", "token_id")
    list_filter = ("kind", "state", "classification", "department")


@admin.register(AssetVersion)
class AssetVersionAdmin(ReadOnlyAdmin):
    list_display = ("asset", "version", "mime_type", "size", "object_key", "created_at")
    search_fields = ("asset__name", "content_hash", "metadata_hash", "object_key")


@admin.register(IntegrityCheck)
class IntegrityCheckAdmin(ReadOnlyAdmin):
    list_display = ("asset_version", "passed", "checked_by", "error_code", "created_at")
    search_fields = ("asset_version__asset__name", "expected_hash", "calculated_hash", "error_code")
    list_filter = ("passed", "error_code")


@admin.register(TransferRequest)
class TransferRequestAdmin(ReadOnlyAdmin):
    list_display = ("asset", "sender", "recipient", "state", "approved_by", "created_at")
    search_fields = ("asset__name", "sender__did", "recipient__did")
    list_filter = ("state",)
