"""Unit tests for Grok and Azure OpenAI LLM adapters + factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.llm.azure_openai_adapter import AzureOpenAIProvider
from app.infrastructure.llm.grok_adapter import GrokProvider
from app.infrastructure.llm.mock_adapter import MockAIProvider
from app.modules.providers.infrastructure.provider_factory import DefaultProviderFactory
from app.shared.ai_types import CompletionRequest


@pytest.mark.asyncio
async def test_grok_complete() -> None:
    provider = GrokProvider(api_key="xai-test", base_url="https://api.x.ai/v1")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "model": "grok-2-latest",
        "choices": [{"message": {"content": "hello from grok"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4},
    }
    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = AsyncMock(return_value=mock_resp)
        client_cls.return_value = client
        result = await provider.complete(CompletionRequest(prompt="hi", model="grok-2-latest"))
    assert result.provider == "grok"
    assert result.text == "hello from grok"
    assert result.tokens_in == 3


@pytest.mark.asyncio
async def test_azure_openai_complete() -> None:
    provider = AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com",
        api_key="key",
        api_version="2024-02-15-preview",
        deployment="gpt-4",
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "model": "gpt-4",
        "choices": [{"message": {"content": "azure hi"}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 2},
    }
    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = AsyncMock(return_value=mock_resp)
        client_cls.return_value = client
        result = await provider.complete(CompletionRequest(prompt="hi"))
    assert result.provider == "azure_openai"
    assert result.text == "azure hi"
    url = client.post.await_args.args[0]
    assert "deployments/gpt-4/chat/completions" in url


def test_factory_known_providers_include_grok_azure() -> None:
    known = DefaultProviderFactory().known_providers()
    assert "grok" in known
    assert "azure_openai" in known
    assert "openai" in known
    assert "gemini" in known
    assert "perplexity" in known


def test_factory_grok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROK_API_KEY", "xai-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        provider = DefaultProviderFactory().create("grok")
        assert isinstance(provider, GrokProvider)
    finally:
        get_settings.cache_clear()


def test_factory_azure_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        provider = DefaultProviderFactory().create("azure_openai")
        assert isinstance(provider, AzureOpenAIProvider)
    finally:
        get_settings.cache_clear()


def test_factory_missing_grok_falls_back_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROK_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        provider = DefaultProviderFactory().create("grok")
        assert isinstance(provider, MockAIProvider)
    finally:
        get_settings.cache_clear()
