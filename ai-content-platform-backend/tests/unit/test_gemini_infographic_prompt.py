"""Tests for the simplified Gemini infographic prompt.

Each case pins a bug the previous structured-slot prompt produced: an emoji
drawn into the headline, a mid-sentence fragment rendered verbatim because
the body was pre-chopped into a `subheadline` slot, and the model being told
never to draw the logo (which forced post-hoc compositing).
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from app.modules.image.application.gemini_infographic_prompt import (
    build_gemini_infographic_prompt,
    strip_emoji,
)
from app.modules.image.application.logo_stamp import should_use_backing
from app.modules.image.application.visual_strategy import VisualStrategyEngine

_BRAND = {
    "name": "Guard IQ",
    "primary_color": "#003366",
    "secondary_color": "#FFFFFF",
    "accent_color": "#0066CC",
}

_LONG_BODY = (
    "Many businesses are leaving their data exposed by sending emails to "
    "'no-reply' addresses. Two researchers bought cheap domains and set up "
    "email listening services. For care, legal, and accountancy practices, "
    "this is a serious risk under GDPR."
)


def _spec(fmt: str = "linkedin_square"):
    draft = {"hook": "Test hook", "body": _LONG_BODY, "content_type": "educational"}
    return VisualStrategyEngine().plan(
        draft,
        _BRAND,
        source_excerpt="",
        visual_style="professional",
        quality="standard",
        image_format=fmt,
        include_logo=True,
        logo_position=None,
        logo_size=None,
        variant_index=1,
        creative_mode="gemini_infographic",
    )


def test_strip_emoji_removes_pictographs_and_tidies_spacing() -> None:
    assert strip_emoji("Think again. \U0001f512") == "Think again."
    assert strip_emoji("Secure ✅ your data now") == "Secure your data now"
    assert strip_emoji("No emoji here.") == "No emoji here."


def test_emoji_never_reaches_the_prompt() -> None:
    draft = {"hook": "Is your webmail safe? \U0001f512", "body": _LONG_BODY}
    positive, _ = build_gemini_infographic_prompt(
        _spec(), brand=_BRAND, draft=draft, logo_as_reference=True
    )
    assert "\U0001f512" not in positive
    assert "Is your webmail safe?" in positive


def test_full_body_is_sent_verbatim_not_truncated() -> None:
    """The old path pre-chopped the body into a subheadline slot, which the
    model then rendered as a cut-off fragment."""
    draft = {"hook": "Test hook", "body": _LONG_BODY}
    positive, _ = build_gemini_infographic_prompt(
        _spec(), brand=_BRAND, draft=draft, logo_as_reference=True
    )
    assert _LONG_BODY in positive


def test_prompt_forbids_rendering_truncated_text() -> None:
    positive, negative = build_gemini_infographic_prompt(
        _spec(), brand=_BRAND, draft={"hook": "h", "body": _LONG_BODY}, logo_as_reference=True
    )
    assert "cut-off" in positive
    assert "truncated" in negative


def test_logo_reference_tells_model_to_place_the_attached_mark() -> None:
    positive, _ = build_gemini_infographic_prompt(
        _spec(), brand=_BRAND, draft={"hook": "h", "body": "b"}, logo_as_reference=True
    )
    assert "A logo image is attached" in positive
    # The old prompt did the opposite — it reserved blank space and banned the
    # model from drawing anything there.
    assert "must be left" not in positive


def _flat_light_canvas() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1080, 1080), (245, 247, 250)).save(buf, format="PNG")
    return buf.getvalue()


def _dark_canvas() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1080, 1080), (18, 26, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _busy_canvas() -> bytes:
    img = Image.new("RGB", (1080, 1080), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    for i in range(0, 1080, 9):
        draw.line([(0, i), (1080, i)], fill=(10, 10, 10), width=4)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_no_backing_plate_on_flat_light_background() -> None:
    """The regression: an unconditional plate painted a visible white box on
    an already-white corner."""
    assert should_use_backing(_flat_light_canvas(), position="bottom_right") is False


def test_backing_plate_used_on_dark_background() -> None:
    assert should_use_backing(_dark_canvas(), position="bottom_right") is True


def test_backing_plate_used_on_busy_background() -> None:
    assert should_use_backing(_busy_canvas(), position="bottom_right") is True
