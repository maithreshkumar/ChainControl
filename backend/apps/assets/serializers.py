from rest_framework import serializers

from .models import Asset, AssetVersion, TransferRequest


class AssetVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetVersion
        exclude = ("wrapped_key", "wrap_nonce", "content_nonce")


class AssetSerializer(serializers.ModelSerializer):
    versions = AssetVersionSerializer(many=True, read_only=True)
    owner_did = serializers.CharField(source="owner_projection.did", allow_null=True, read_only=True)

    class Meta:
        model = Asset
        fields = ("id", "name", "kind", "classification", "department", "created_by", "owner_projection", "owner_did", "state", "token_id", "serial_number", "custody_identifier", "versions", "created_at")
        read_only_fields = ("created_by", "owner_projection", "department", "state", "token_id")


class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferRequest
        fields = "__all__"
        read_only_fields = ("sender", "state", "recipient_acted_at", "approved_by", "approved_at", "blockchain_transaction")
