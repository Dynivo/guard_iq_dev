"""Intelligence module ports — embeddings, clustering, relevance scoring."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass
class EmbeddingResult:
    vector: list[float]
    model_version: str
    dimensions: int


@dataclass
class RelevanceResult:
    score: int
    sector: str | None
    framework: str | None
    audience: str | None
    angle: str | None
    reason: str | None


class EmbeddingProvider(Protocol):
    """Port for text embedding generation."""

    async def embed(self, text: str) -> EmbeddingResult: ...

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]: ...


class VectorStore(Protocol):
    """Port for vector similarity search."""

    async def upsert(self, collection: str, doc_id: str, vector: list[float], payload: dict) -> None: ...

    async def search(self, collection: str, vector: list[float], top_k: int) -> list[dict]: ...


class Clusterer(Protocol):
    """Port for article clustering by embedding similarity."""

    async def cluster(self, org_id: uuid.UUID, article_ids: list[uuid.UUID]) -> list[list[uuid.UUID]]: ...


class RelevanceScorer(Protocol):
    """Port for article relevance scoring using the client profile."""

    async def score(self, org_id: uuid.UUID, article_id: uuid.UUID) -> RelevanceResult: ...
