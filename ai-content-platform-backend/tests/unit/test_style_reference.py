"""Tests for the house-style reference image plumbing.

Covers the chain: bundled asset -> ReferenceImagePolicy -> provider contents,
including that each reference's prompt_hint is actually sent (without it the
model receives an unlabeled image and can't tell a style exemplar from
something to reproduce literally).
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.infrastructure.image_generation.gemini_infographic_provider import (
    GeminiInfographicProvider,
)
from app.modules.image.application import brand_assets
from app.modules.image.application.reference_policy import ReferenceImagePolicy
from app.modules.image.domain.models import ImageGenerationRequest


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 32), (10, 40, 60)).save(buf, format="PNG")
    return buf.getvalue()


def test_no_style_reference_bundled_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absent asset must leave generation exactly as it was — text prompt only."""
    monkeypatch.setattr(brand_assets, "default_style_reference_path", lambda: None)
    assert brand_assets.default_style_reference() is None

    bundle = ReferenceImagePolicy().resolve(
        mode="auto", include_logo=False, logo_bytes=None, brand_style_bytes=None
    )
    assert bundle.provider_references() == []


def test_style_reference_is_included_with_its_hint() -> None:
    bundle = ReferenceImagePolicy().resolve(
        mode="auto",
        include_logo=False,
        logo_bytes=None,
        brand_style_bytes=_png_bytes(),
        brand_style_mime="image/png",
    )
    refs = bundle.provider_references()
    assert len(refs) == 1
    assert refs[0]["role"] == "brand_style"
    assert refs[0]["mime_type"] == "image/png"
    hint = refs[0]["prompt_hint"]
    assert "STYLE REFERENCE" in hint
    # Must tell the model to take style but not content, or it copies the
    # exemplar's headline/stats into the new creative.
    assert "Do NOT copy" in hint


def test_style_reference_mime_is_honoured_for_non_png() -> None:
    bundle = ReferenceImagePolicy().resolve(
        mode="auto",
        include_logo=False,
        logo_bytes=None,
        brand_style_bytes=_png_bytes(),
        brand_style_mime="image/jpeg",
    )
    assert bundle.provider_references()[0]["mime_type"] == "image/jpeg"


def test_provider_sends_hint_text_before_reference_image() -> None:
    provider = GeminiInfographicProvider()
    request = ImageGenerationRequest(
        prompt="MAIN PROMPT",
        width=1080,
        height=1080,
        style="gemini_infographic",
        parameters={
            "reference_images": [
                {
                    "role": "brand_style",
                    "bytes": _png_bytes(),
                    "mime_type": "image/png",
                    "prompt_hint": "STYLE REFERENCE — match visual language only.",
                }
            ]
        },
    )
    parts = provider._build_contents(request)
    # main prompt, hint text, image bytes
    assert len(parts) == 3
    texts = [getattr(p, "text", None) for p in parts]
    assert texts[0] == "MAIN PROMPT"
    assert texts[1] == "STYLE REFERENCE — match visual language only."
    assert getattr(parts[2], "inline_data", None) is not None
