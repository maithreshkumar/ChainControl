from contextlib import contextmanager

import redis
from django.conf import settings

from apps.common.errors import DomainError


class NonceManager:
    def __init__(self):
        self.redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    @contextmanager
    def reserve(self, web3, address):
        lock = self.redis.lock(f"chaincontrol:nonce-lock:{address.lower()}", timeout=30, blocking_timeout=10)
        try:
            acquired = lock.acquire()
        except redis.RedisError as exc:
            raise DomainError("NONCE_SERVICE_UNAVAILABLE", "Nonce coordination is unavailable.", status_code=503) from exc
        if not acquired:
            raise DomainError("NONCE_CONFLICT", "Could not reserve a transaction nonce.", status_code=409)
        try:
            key = f"chaincontrol:next-nonce:{address.lower()}"
            network_nonce = web3.eth.get_transaction_count(address, "pending")
            cached = self.redis.get(key)
            nonce = max(network_nonce, int(cached)) if cached is not None else network_nonce
            self.redis.set(key, nonce + 1, ex=3600)
            yield nonce
        finally:
            try:
                lock.release()
            except redis.RedisError:
                pass

