from django.conf import settings
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from apps.common.errors import DomainError


def get_web3(provider_url=None) -> Web3:
    client = Web3(Web3.HTTPProvider(provider_url or settings.WEB3_PROVIDER_URL, request_kwargs={"timeout": 10}))
    # Besu QBFT encodes validator seals in a larger ``extraData`` field than
    # Ethereum mainnet.  Normalize that field before Web3 decodes blocks.
    client.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not client.is_connected():
        raise DomainError("BLOCKCHAIN_UNAVAILABLE", "The blockchain RPC endpoint is unavailable.", status_code=503)
    return client
