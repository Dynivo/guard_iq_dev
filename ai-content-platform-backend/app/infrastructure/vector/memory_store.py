"""In-memory vector store for tests and local fallback."""

from __future__ import annotations

import math
from collections import defaultdict


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
