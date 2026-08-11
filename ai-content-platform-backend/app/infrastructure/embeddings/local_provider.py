"""Local / hash embedding provider."""

from __future__ import annotations

import hashlib
import struct

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.knowledge.domain.models import EmbeddingResult

logger = get_logger(__name__)

_DEMO_DIMENSIONS = 384


class LocalEmbeddingProvider:
    """Local embedding: optional HTTP service, else deterministic hash vector."""

    def __init__(self, dimensions: int = _DEMO_DIMENSIONS) -> None:
        self._dimensions = dimensions
        self._local_url = get_settings().LOCAL_EMBEDDING_URL

    async def embed(self, text: str) -> EmbeddingResult:
        if self._local_url:
            return await self._embed_via_service(text)
        return self._hash_embed(text)

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        return [await self.embed(t) for t in texts]

    def _hash_embed(self, text: str) -> EmbeddingResult:
        features: list[float] = []
        for i in range(self._dimensions):
            chunk = f"{text}:{i}".encode()
            h = hashlib.sha256(chunk).digest()
            val = struct.unpack("f", h[:4])[0]
            features.append((val % 2.0) - 1.0)
        norm = sum(x * x for x in features) ** 0.5
        if norm > 0:
            features = [x / norm for x in features]
        return EmbeddingResult(
            vector=features,
            model_version="hash-v1",
            dimensions=self._dimensions,
        )

    async def _embed_via_service(self, text: str) -> EmbeddingResult:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._local_url.rstrip('/')}/embed",
                    json={"text": text},
                )
                resp.raise_for_status()
                data = resp.json()
                return EmbeddingResult(
                    vector=data["vector"],
                    model_version=data.get("model", "local"),
                    dimensions=len(data["vector"]),
                )
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Local embedding unavailable (%s), using hash", exc)
            return self._hash_embed(text)
