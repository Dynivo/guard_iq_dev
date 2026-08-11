"""Namespaced AI cache facades for Knowledge Engine stages."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.modules.ai_cache.domain.ports import AICachePort


class CacheNamespace:
    EMBEDDING = "embedding"
    RETRIEVAL = "retrieval"
    RANKING = "ranking"
    CONTEXT = "context"
    PROMPT = "prompt"
    PLANNER = "planner"
    STRATEGY = "strategy"
    TOPIC = "topic"
    TREND = "trend"
    GENERATION = "generation"
    VALIDATION = "validation"
    FORMATTER = "formatter"
    NEWS_FEED = "news:feed"
    NEWS_ARTICLE = "news:article"
    NEWS_META = "news:meta"
    NEWS_CONNECTOR = "news:connector"


class NamespacedAICache:
    """Wraps a single AICachePort with stage prefixes — no separate Redis clients."""

    def __init__(self, inner: AICachePort) -> None:
        self._inner = inner

    def _key(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    async def get(self, namespace: str, key: str) -> dict | None:
        return await self._inner.get(self._key(namespace, key))

    async def set(
        self, namespace: str, key: str, value: dict, ttl_seconds: int
    ) -> None:
        await self._inner.set(self._key(namespace, key), value, ttl_seconds)

    async def invalidate(self, namespace: str, prefix: str = "") -> None:
        await self._inner.invalidate(self._key(namespace, prefix))


class EmbeddingCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 3600) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    @staticmethod
    def key_for(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    async def get(self, text: str) -> dict | None:
        return await self._cache.get(CacheNamespace.EMBEDDING, self.key_for(text))

    async def set(self, text: str, value: dict) -> None:
        await self._cache.set(
            CacheNamespace.EMBEDDING, self.key_for(text), value, self._ttl
        )


class RetrievalCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 600) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    @staticmethod
    def key_for(payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    async def get(self, payload: dict[str, Any]) -> dict | None:
        return await self._cache.get(CacheNamespace.RETRIEVAL, self.key_for(payload))

    async def set(self, payload: dict[str, Any], value: dict) -> None:
        await self._cache.set(
            CacheNamespace.RETRIEVAL, self.key_for(payload), value, self._ttl
        )


class RankingCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 600) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    @staticmethod
    def key_for(payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    async def get(self, payload: dict[str, Any]) -> dict | None:
        return await self._cache.get(CacheNamespace.RANKING, self.key_for(payload))

    async def set(self, payload: dict[str, Any], value: dict) -> None:
        await self._cache.set(
            CacheNamespace.RANKING, self.key_for(payload), value, self._ttl
        )


class ContextCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 600) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    @staticmethod
    def key_for(payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    async def get(self, payload: dict[str, Any]) -> dict | None:
        return await self._cache.get(CacheNamespace.CONTEXT, self.key_for(payload))

    async def set(self, payload: dict[str, Any], value: dict) -> None:
        await self._cache.set(
            CacheNamespace.CONTEXT, self.key_for(payload), value, self._ttl
        )


class PromptCache:
    """Compiled/definition/eval cache under prompt: namespace (M7)."""

    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 600) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, key: str) -> dict | None:
        return await self._cache.get(CacheNamespace.PROMPT, key)

    async def set(self, key: str, value: dict) -> None:
        await self._cache.set(CacheNamespace.PROMPT, key, value, self._ttl)


class NewsFeedCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 300) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, key: str) -> dict | None:
        return await self._cache.get(CacheNamespace.NEWS_FEED, key)

    async def set(self, key: str, value: dict) -> None:
        await self._cache.set(CacheNamespace.NEWS_FEED, key, value, self._ttl)


class NewsArticleCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 600) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, key: str) -> dict | None:
        return await self._cache.get(CacheNamespace.NEWS_ARTICLE, key)

    async def set(self, key: str, value: dict) -> None:
        await self._cache.set(CacheNamespace.NEWS_ARTICLE, key, value, self._ttl)


class NewsConnectorCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 120) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, key: str) -> dict | None:
        return await self._cache.get(CacheNamespace.NEWS_CONNECTOR, key)

    async def set(self, key: str, value: dict) -> None:
        await self._cache.set(CacheNamespace.NEWS_CONNECTOR, key, value, self._ttl)


class NewsTrendCache:
    """Topic trend metrics under CacheNamespace.TREND (news Trend Engine)."""

    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 600) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, topic_key: str) -> dict | None:
        return await self._cache.get(CacheNamespace.TREND, topic_key)

    async def set(self, topic_key: str, value: dict) -> None:
        await self._cache.set(CacheNamespace.TREND, topic_key, value, self._ttl)


class GenerationCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 600) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, key: str) -> dict | None:
        return await self._cache.get(CacheNamespace.GENERATION, key)

    async def set(self, key: str, value: dict) -> None:
        await self._cache.set(CacheNamespace.GENERATION, key, value, self._ttl)


class ValidationCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 300) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, key: str) -> dict | None:
        return await self._cache.get(CacheNamespace.VALIDATION, key)

    async def set(self, key: str, value: dict) -> None:
        await self._cache.set(CacheNamespace.VALIDATION, key, value, self._ttl)


class FormatterCache:
    def __init__(self, cache: NamespacedAICache, *, ttl_seconds: int = 300) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, key: str) -> dict | None:
        return await self._cache.get(CacheNamespace.FORMATTER, key)

    async def set(self, key: str, value: dict) -> None:
        await self._cache.set(CacheNamespace.FORMATTER, key, value, self._ttl)
