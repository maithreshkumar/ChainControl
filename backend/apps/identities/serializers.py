from rest_framework import serializers

from .models import DecentralizedIdentity


class IdentitySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = DecentralizedIdentity
        fields = ("id", "user", "username", "did", "controller_address", "state", "key_version", "registration_tx_hash", "created_at")
        read_only_fields = ("state", "key_version", "registration_tx_hash", "created_at")


class ChallengeCreateSerializer(serializers.Serializer):
    purpose = serializers.CharField(max_length=80)


class ChallengeVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    nonce = serializers.CharField(max_length=128)
    signature = serializers.CharField(max_length=512)

