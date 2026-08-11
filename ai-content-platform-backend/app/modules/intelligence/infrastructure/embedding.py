"""Intelligence embedding alias — resolves via shared embedding factory."""

from __future__ import annotations

from app.infrastructure.embeddings.factory import get_embedding_provider
from app.infrastructure.embeddings.local_provider import LocalEmbeddingProvider
from app.modules.knowledge.domain.models import EmbeddingResult

# Backward-compatible name for tests / callers that expect a concrete class.
SimpleEmbeddingProvider = LocalEmbeddingProvider

__all__ = [
    "SimpleEmbeddingProvider",
    "LocalEmbeddingProvider",
    "EmbeddingResult",
    "get_embedding_provider",
]
