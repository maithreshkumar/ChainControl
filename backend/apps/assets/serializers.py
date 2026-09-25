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
        fields = ("id", "name", "kind", "asset_type", "classification", "department", "created_by", "owner_projection", "owner_did", "state", "token_id", "serial_number", "custody_identifier", "versions", "created_at")
        read_only_fields = ("asset_type", "created_by", "owner_projection", "department", "state", "token_id")


class TransferSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    token_id = serializers.IntegerField(source="asset.token_id", allow_null=True, read_only=True)
    sender_username = serializers.CharField(source="sender.user.username", read_only=True)
    sender_did = serializers.CharField(source="sender.did", read_only=True)
    recipient_username = serializers.CharField(source="recipient.user.username", read_only=True)
    recipient_did = serializers.CharField(source="recipient.did", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", allow_null=True, read_only=True)

    class Meta:
        model = TransferRequest
        fields = "__all__"
        read_only_fields = ("sender", "state", "recipient_acted_at", "approved_by", "approved_at", "blockchain_transaction")
