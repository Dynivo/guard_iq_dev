"""Local, dependency-free vector store + embedding fallback for the Knowledge Engine.

The Knowledge Engine's semantic/hybrid retrieval strategies only ever run
in-memory (no external vector DB is configured for this deployment) — this
module provides that self-contained implementation.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections import defaultdict

from app.modules.knowledge.domain.models import EmbeddingResult

_DEMO_DIMENSIONS = 384


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, tuple[list[float], dict]]] = defaultdict(dict)

    async def upsert(
        self, collection: str, doc_id: str, vector: list[float], payload: dict
    ) -> None:
        self._data[collection][doc_id] = (list(vector), dict(payload))

    async def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        *,
        filters: dict | None = None,
    ) -> list[dict]:
        rows = []
        for doc_id, (vec, payload) in self._data.get(collection, {}).items():
            if filters:
                if any(payload.get(k) != v for k, v in filters.items()):
                    continue
            rows.append(
                {
                    "id": doc_id,
                    "score": _cosine(vector, vec),
                    "payload": payload,
                }
            )
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows[:top_k]


class LocalEmbeddingProvider:
    """Deterministic hash-based embedding — no external service, no API key."""

    def __init__(self, dimensions: int = _DEMO_DIMENSIONS) -> None:
        self._dimensions = dimensions

    async def embed(self, text: str) -> EmbeddingResult:
        return self._hash_embed(text)

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        return [self._hash_embed(t) for t in texts]

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
