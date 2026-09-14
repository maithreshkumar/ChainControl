from apps.common.errors import DomainError

from .client import get_web3
from .models import ContractDeployment


def get_contract(name: str):
    deployment = ContractDeployment.objects.filter(name=name, active=True).order_by("-created_at").first()
    if deployment is None:
        raise DomainError("CONTRACT_NOT_DEPLOYED", f"{name} has no active deployment.", status_code=503)
    web3 = get_web3()
    return web3, web3.eth.contract(address=web3.to_checksum_address(deployment.address), abi=deployment.abi)

