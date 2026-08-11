"""Qdrant vector store adapter with org filter support."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class QdrantVectorStore:
    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self._url = url or settings.QDRANT_URL
        self._api_key = api_key if api_key is not None else settings.QDRANT_API_KEY
        self._client: object | None = None
        self._available = False
        self._init_attempted = False

    async def _ensure_client(self) -> bool:
        if self._init_attempted:
            return self._available
        self._init_attempted = True
        try:
            from qdrant_client import AsyncQdrantClient

            kwargs: dict = {"url": self._url, "timeout": 5.0}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            self._client = AsyncQdrantClient(**kwargs)
            await self._client.get_collections()  # type: ignore[union-attr]
            self._available = True
            logger.info("Qdrant connected at %s", self._url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant unavailable (%s)", exc)
            self._available = False
        return self._available

    async def _ensure_collection(self, collection: str, dimensions: int) -> None:
        if not self._available or self._client is None:
            return
        try:
            from qdrant_client.models import Distance, VectorParams

            collections = await self._client.get_collections()  # type: ignore[union-attr]
            names = [c.name for c in collections.collections]
            if collection not in names:
                await self._client.create_collection(  # type: ignore[union-attr]
                    collection_name=collection,
                    vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to ensure collection '%s': %s", collection, exc)

    async def upsert(
        self, collection: str, doc_id: str, vector: list[float], payload: dict
    ) -> None:
        if not await self._ensure_client():
            return
        await self._ensure_collection(collection, len(vector))
        try:
            from qdrant_client.models import PointStruct

            point = PointStruct(id=doc_id, vector=vector, payload=payload)
            await self._client.upsert(  # type: ignore[union-attr]
                collection_name=collection, points=[point]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant upsert failed for %s: %s", doc_id, exc)

    async def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        *,
        filters: dict | None = None,
    ) -> list[dict]:
        if not await self._ensure_client():
            return []
        try:
            query_filter = None
            if filters:
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                must = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filters.items()
                ]
                query_filter = Filter(must=must)
            results = await self._client.search(  # type: ignore[union-attr]
                collection_name=collection,
                query_vector=vector,
                limit=top_k,
                query_filter=query_filter,
            )
            return [
                {"id": str(r.id), "score": r.score, "payload": r.payload or {}}
                for r in results
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant search failed: %s", exc)
            return []
