from rest_framework import serializers

from .models import BlockchainEvent, BlockchainTransaction


class BlockchainTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockchainTransaction
        fields = "__all__"


class BlockchainEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockchainEvent
        fields = "__all__"

