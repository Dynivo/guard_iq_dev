"""Resolve EmbeddingProvider from configuration."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.embeddings.local_provider import LocalEmbeddingProvider
from app.modules.knowledge.domain.ports import EmbeddingProvider

logger = get_logger(__name__)


def get_embedding_provider(provider_name: str | None = None) -> EmbeddingProvider:
    """Return local | openai | azure_openai embedding adapter.

    Default is ``local`` (hash / LOCAL_EMBEDDING_URL) for CI safety.
    Changing embedding dimensions requires a new Qdrant collection / reindex.
    """
    settings = get_settings()
    name = (provider_name or settings.EMBEDDING_PROVIDER or "local").lower().strip()

    if name in {"openai"}:
        if not settings.OPENAI_API_KEY.strip():
            logger.warning(
                "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY missing; using local"
            )
            return LocalEmbeddingProvider()
        from app.infrastructure.embeddings.openai_provider import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider()

    if name in {"azure_openai", "azure"}:
        if not (
            settings.AZURE_OPENAI_ENDPOINT.strip()
            and settings.AZURE_OPENAI_API_KEY.strip()
            and settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT.strip()
        ):
            logger.warning(
                "EMBEDDING_PROVIDER=azure_openai but Azure credentials incomplete; using local"
            )
            return LocalEmbeddingProvider()
        from app.infrastructure.embeddings.azure_openai_provider import (
            AzureOpenAIEmbeddingProvider,
        )

        return AzureOpenAIEmbeddingProvider()

    if name and name not in {"local", "hash", ""}:
        logger.warning("Unknown EMBEDDING_PROVIDER=%s; falling back to local", name)

    return LocalEmbeddingProvider()
