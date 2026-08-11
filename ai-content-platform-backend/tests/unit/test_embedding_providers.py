"""Unit tests for embedding provider factory and OpenAI/Azure adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppError
from app.infrastructure.embeddings.azure_openai_provider import AzureOpenAIEmbeddingProvider
from app.infrastructure.embeddings.factory import get_embedding_provider
from app.infrastructure.embeddings.local_provider import LocalEmbeddingProvider
from app.infrastructure.embeddings.openai_provider import OpenAIEmbeddingProvider


@pytest.mark.asyncio
async def test_openai_embedding_success() -> None:
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(
                return_value={
                    "model": "text-embedding-3-small",
                    "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
                }
            ),
        )
    )
    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        model="text-embedding-3-small",
        dimensions=3,
        client=mock_client,
    )
    result = await provider.embed("hello")
    assert result.dimensions == 3
    assert result.vector == [0.1, 0.2, 0.3]
    assert "text-embedding" in result.model_version


@pytest.mark.asyncio
async def test_openai_embedding_missing_key() -> None:
    provider = OpenAIEmbeddingProvider(api_key="", client=MagicMock())
    with pytest.raises(AppError, match="OPENAI_API_KEY"):
        await provider.embed("x")


@pytest.mark.asyncio
async def test_azure_embedding_success() -> None:
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(
                return_value={
                    "model": "text-embedding-3-small",
                    "data": [{"index": 0, "embedding": [0.5, 0.5]}],
                }
            ),
        )
    )
    provider = AzureOpenAIEmbeddingProvider(
        endpoint="https://example.openai.azure.com",
        api_key="key",
        api_version="2024-02-15-preview",
        deployment="text-embedding-3-small",
        dimensions=2,
        client=mock_client,
    )
    result = await provider.embed("hello")
    assert result.vector == [0.5, 0.5]
    mock_client.post.assert_awaited_once()
    url = mock_client.post.await_args.args[0]
    assert "deployments/text-embedding-3-small/embeddings" in url
    assert "api-version=" in url


def test_factory_local_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert isinstance(get_embedding_provider(), LocalEmbeddingProvider)
    finally:
        get_settings.cache_clear()


def test_factory_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert isinstance(get_embedding_provider(), OpenAIEmbeddingProvider)
    finally:
        get_settings.cache_clear()


def test_factory_azure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert isinstance(get_embedding_provider(), AzureOpenAIEmbeddingProvider)
    finally:
        get_settings.cache_clear()


def test_factory_openai_missing_key_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert isinstance(get_embedding_provider(), LocalEmbeddingProvider)
    finally:
        get_settings.cache_clear()
