from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.modules.image.application.visual_critic import VisualCreativeCritic
from app.modules.image.application.visual_strategy import VisualStrategyEngine


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 64), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _spec():
    return VisualStrategyEngine().plan(
        {"hook": "Secure your account", "body": "Use MFA.", "content_type": "educational"},
        {
            "name": "Guard IQ",
            "primary_color": "#003366",
            "secondary_color": "#FFFFFF",
            "accent_color": "#0066CC",
        },
        source_excerpt="",
        visual_style="professional",
        quality="standard",
        image_format="linkedin_square",
        include_logo=True,
        logo_position=None,
        logo_size=None,
        variant_index=1,
        creative_mode="gemini_infographic",
    )


@pytest.mark.asyncio
async def test_visual_critic_receives_real_image_bytes() -> None:
    expected = _png()
    captured: dict[str, object] = {}

    async def complete(prompt: str, image_bytes: bytes) -> str:
        captured["prompt"] = prompt
        captured["image_bytes"] = image_bytes
        return (
            '{"overall":91,"scores":{"composition":91,"legibility":92},'
            '"issues":[],"recommendations":[],"flags":{"logo_ok":true}}'
        )

    result = await VisualCreativeCritic(multimodal_complete=complete).critique(
        expected,
        _spec(),
    )

    assert captured["image_bytes"] == expected
    assert "BASE64" not in str(captured["prompt"])
    assert result.overall == 91
    assert result.passed is True
