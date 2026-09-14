from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import BlockchainEvent, BlockchainTransaction, ContractDeployment


@admin.register(BlockchainTransaction)
class BlockchainTransactionAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "operation", "status", "tx_hash", "block_number")
    search_fields = ("tx_hash", "operation", "actor_did", "related_object_id")
    list_filter = ("status", "operation")


@admin.register(BlockchainEvent)
class BlockchainEventAdmin(ReadOnlyAdmin):
    list_display = ("block_number", "event_name", "contract_name", "tx_hash", "log_index")
    search_fields = ("tx_hash", "event_name", "contract_name")
    list_filter = ("event_name", "contract_name")


@admin.register(ContractDeployment)
class ContractDeploymentAdmin(ReadOnlyAdmin):
    list_display = ("name", "version", "chain_id", "address", "active", "deployment_block")
    search_fields = ("name", "version", "address", "deployment_tx_hash")
    list_filter = ("active", "chain_id")
