from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.audit.services import record_audit

from .models import BlockchainNode, ValidatorGovernanceOperation
from .services import refresh_managed_node_health, refresh_validator_operation


@shared_task
def monitor_network_nodes():
    managed_refreshed = refresh_managed_node_health()
    threshold = timezone.now() - timedelta(seconds=settings.NETWORK_NODE_OFFLINE_SECONDS)
    stale = BlockchainNode.objects.filter(
        status__in=[BlockchainNode.Status.CONNECTING, BlockchainNode.Status.SYNCING, BlockchainNode.Status.ONLINE, BlockchainNode.Status.DEGRADED],
        last_seen__lt=threshold,
    )
    for node in stale:
        node.status = BlockchainNode.Status.OFFLINE
        node.save(update_fields=["status", "updated_at"])
        record_audit(action="NODE_OFFLINE", object_type="BlockchainNode", object_id=node.id, details={"last_seen": node.last_seen.isoformat() if node.last_seen else None})
    operations = ValidatorGovernanceOperation.objects.filter(status=ValidatorGovernanceOperation.Status.IN_PROGRESS)
    for operation in operations:
        refresh_validator_operation(operation)
    return {"managed_refreshed": managed_refreshed, "offline": stale.count(), "governance_checked": operations.count()}
