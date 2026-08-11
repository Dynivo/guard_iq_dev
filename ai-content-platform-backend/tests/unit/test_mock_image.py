"""Unit tests for MockImageGenerator."""

from __future__ import annotations

import asyncio

from app.infrastructure.image_generation.mock_generator import MockImageGenerator
from app.modules.image.domain.ports import ImageGenerationRequest


def test_mock_image_generates_png() -> None:
    gen = MockImageGenerator()
    result = asyncio.run(
        gen.generate(ImageGenerationRequest(prompt="BEC invoice comparison", width=400, height=500))
    )
    assert result.provider == "mock"
    assert result.width == 400
    assert result.height == 500
    assert result.image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
