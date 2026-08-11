"""Logo corner detection + typography default resolution."""

from __future__ import annotations

import io

from app.modules.brand_intelligence.application.logo_placement import (
    detect_logo_corner_from_bytes,
    majority_logo_position,
    resolve_logo_placement_defaults,
)


def _png_with_corner_badge(position: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (400, 400), (240, 240, 240, 255))
    draw = ImageDraw.Draw(img)
    # Quiet center
    draw.rectangle((120, 120, 280, 280), fill=(220, 220, 220, 255))
    badge = (20, 20, 90, 90)
    if position == "top_right":
        badge = (310, 20, 380, 90)
    elif position == "bottom_left":
        badge = (20, 310, 90, 380)
    elif position == "bottom_right":
        badge = (310, 310, 380, 380)
    draw.ellipse(badge, fill=(10, 31, 43, 255))
    draw.rectangle(
        (badge[0] + 10, badge[1] + 25, badge[2] - 10, badge[3] - 25),
        fill=(26, 92, 176, 255),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_detect_logo_bottom_right() -> None:
    raw = _png_with_corner_badge("bottom_right")
    result = detect_logo_corner_from_bytes(raw)
    assert result["logo_presence"] is True
    assert result["logo_position"] == "bottom_right"


def test_majority_logo_position() -> None:
    samples = [
        {"logo_presence": True, "logo_position": "bottom_right"},
        {"logo_presence": True, "logo_position": "bottom_right"},
        {"logo_presence": True, "logo_position": "top_left"},
        {"logo_presence": False, "logo_position": "center"},
    ]
    assert majority_logo_position(samples) == "bottom_right"


def test_resolve_defaults_optional_and_learned() -> None:
    defaults = resolve_logo_placement_defaults(
        {"preferred_logo_position": "top_left"},
        has_logo_asset=True,
    )
    assert defaults["include_logo"] is False
    assert defaults["position"] == "top_left"
    assert defaults["learned_position"] == "top_left"

    opted = resolve_logo_placement_defaults(
        {"preferred_logo_position": "bottom_right"},
        has_logo_asset=True,
        override={"include_logo": True, "position": "brand_default", "size": "l"},
    )
    assert opted["include_logo"] is True
    assert opted["position"] == "bottom_right"
    assert opted["size"] == "l"
