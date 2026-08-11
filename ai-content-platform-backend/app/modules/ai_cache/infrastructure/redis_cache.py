"""Redis AI cache adapter."""

from __future__ import annotations

import json

from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisAICache:
    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(self._url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> dict | None:
        try:
            raw = await self._get_client().get(key)
        except Exception:  # noqa: BLE001
            logger.exception("ai_cache.redis_get_failed")
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        try:
            payload = json.dumps(value)
            client = self._get_client()
            if ttl_seconds > 0:
                await client.set(key, payload, ex=ttl_seconds)
            else:
                await client.set(key, payload)
        except Exception:  # noqa: BLE001
            logger.exception("ai_cache.redis_set_failed")

    async def invalidate(self, prefix: str) -> None:
        try:
            client = self._get_client()
            async for key in client.scan_iter(match=f"{prefix}*"):
                await client.delete(key)
        except Exception:  # noqa: BLE001
            logger.exception("ai_cache.redis_invalidate_failed")
