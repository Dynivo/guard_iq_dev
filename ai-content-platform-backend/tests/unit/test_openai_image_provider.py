"""Unit tests for OpenAIImageProvider (mocked SDK — no network)."""

from __future__ import annotations

import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.core.exceptions import AppError
from app.infrastructure.image_generation.factory import get_image_generator
from app.infrastructure.image_generation.openai_provider import (
    OpenAIImageProvider,
    estimate_image_cost,
    map_size,
)
from app.modules.image.domain.models import ImageGenerationRequest


def _tiny_png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "#112233").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_map_size_portrait_landscape_square() -> None:
    cfg = {
        "allowed_sizes": ["1024x1024", "1024x1536", "1536x1024", "auto"],
        "size_map": [
            {"name": "square", "min_ratio": 0.85, "max_ratio": 1.15, "size": "1024x1024"},
            {"name": "portrait", "min_ratio": 0.0, "max_ratio": 0.85, "size": "1024x1536"},
            {"name": "landscape", "min_ratio": 1.15, "max_ratio": 99.0, "size": "1536x1024"},
        ],
    }
    assert map_size(1080, 1350, cfg) == "1024x1536"
    assert map_size(1920, 1080, cfg) == "1536x1024"
    assert map_size(1024, 1024, cfg) == "1024x1024"


def test_estimate_image_cost_from_pricing() -> None:
    pricing = {
        "image_generation": {
            "openai": {
                "models": {
                    "gpt-image-1": {"quality": {"low": 0.02, "medium": 0.07, "high": 0.19}},
                }
            }
        }
    }
    assert estimate_image_cost("gpt-image-1", "high", pricing=pricing) == 0.19
    assert estimate_image_cost("gpt-image-1", "medium", pricing=pricing) == 0.07


@pytest.mark.asyncio
async def test_generate_success_b64_png() -> None:
    b64 = _tiny_png_b64()
    mock_client = MagicMock()
    mock_client.images.generate = AsyncMock(
        return_value=SimpleNamespace(data=[SimpleNamespace(b64_json=b64, url=None)])
    )
    provider = OpenAIImageProvider(
        api_key="sk-test",
        model="gpt-image-1",
        client=mock_client,
        provider_config={
            "defaults": {"quality": "medium", "output_format": "png"},
            "allowed_sizes": ["1024x1024", "1024x1536", "1536x1024"],
            "size_map": [
                {"min_ratio": 0.0, "max_ratio": 0.85, "size": "1024x1536"},
                {"min_ratio": 0.85, "max_ratio": 1.15, "size": "1024x1024"},
                {"min_ratio": 1.15, "max_ratio": 99.0, "size": "1536x1024"},
            ],
        },
        pricing_config={
            "image_generation": {
                "openai": {
                    "models": {
                        "gpt-image-1": {"quality": {"medium": 0.07}},
                    }
                }
            }
        },
    )
    result = await provider.generate(
        ImageGenerationRequest(
            prompt="professional consulting illustration",
            width=1080,
            height=1350,
            metadata={"correlation_id": "corr-1", "request_id": "req-1"},
        )
    )
    assert result.provider == "openai"
    assert result.model == "gpt-image-1"
    assert result.image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert result.cost_estimate == 0.07
    assert result.metadata["api_size"] == "1024x1536"
    assert result.metadata["correlation_id"] == "corr-1"
    assert result.metadata["request_id"] == "req-1"
    assert result.latency_ms >= 0
    mock_client.images.generate.assert_awaited_once()
    call_kwargs = mock_client.images.generate.await_args.kwargs
    assert call_kwargs["prompt"] == "professional consulting illustration"
    assert call_kwargs["size"] == "1024x1536"
    assert call_kwargs["quality"] == "medium"


@pytest.mark.asyncio
async def test_missing_api_key_raises() -> None:
    provider = OpenAIImageProvider(api_key="", client=MagicMock())
    with pytest.raises(AppError, match="OPENAI_API_KEY"):
        await provider.generate(ImageGenerationRequest(prompt="x"))


@pytest.mark.asyncio
async def test_api_error_propagates() -> None:
    from openai import APIError

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.request = MagicMock()
    mock_client.images.generate = AsyncMock(
        side_effect=APIError(
            message="timeout",
            request=mock_response.request,
            body=None,
        )
    )
    provider = OpenAIImageProvider(api_key="sk-test", client=mock_client)
    with pytest.raises(AppError, match="OpenAI Images API error"):
        await provider.generate(ImageGenerationRequest(prompt="x"))


def test_factory_openai_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        from app.infrastructure.image_generation.openai_provider import OpenAIImageProvider

        provider = get_image_generator("openai")
        assert isinstance(provider, OpenAIImageProvider)
    finally:
        get_settings.cache_clear()


def test_factory_rejects_removed_and_unknown_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_PROVIDER", "gemini")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="Unknown image provider"):
            get_image_generator("mock")
        with pytest.raises(ValueError, match="Unknown image provider"):
            get_image_generator("unknown-cloud")
    finally:
        get_settings.cache_clear()


def test_factory_comfyui_branch() -> None:
    with patch(
        "app.infrastructure.image_generation.factory.ComfyUIAdapter"
    ) as mock_cls:
        mock_cls.return_value = MagicMock()
        provider = get_image_generator("comfyui")
        mock_cls.assert_called_once()
        assert provider is mock_cls.return_value
