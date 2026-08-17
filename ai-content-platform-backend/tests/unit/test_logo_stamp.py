"""Tests for content-aware logo placement and the backing-plate stamp."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from app.modules.image.application.logo_stamp import (
    pick_best_corner,
    stamp_brand_logo,
)


def _busy_canvas_with_flat_patch(flat_box: tuple[int, int, int, int]) -> bytes:
    """1080x1350 canvas with a noisy grid everywhere except one flat patch."""
    canvas = Image.new("RGB", (1080, 1350), (30, 40, 60))
    draw = ImageDraw.Draw(canvas)
    for y in range(0, 1350, 15):
        draw.line([(0, y), (1080, y)], fill=(200, 60, 60), width=3)
    for x in range(0, 1080, 15):
        draw.line([(x, 0), (x, 1350)], fill=(60, 200, 60), width=3)
    draw.rectangle(flat_box, fill=(245, 245, 245))
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _solid_logo_bytes() -> bytes:
    logo = Image.new("RGBA", (200, 200), (10, 40, 60, 255))
    buf = BytesIO()
    logo.save(buf, format="PNG")
    return buf.getvalue()


def test_pick_best_corner_finds_the_flat_region() -> None:
    canvas_bytes = _busy_canvas_with_flat_patch((0, 0, 220, 220))  # top-left flat
    assert pick_best_corner(canvas_bytes) == "top_left"


def test_pick_best_corner_follows_flat_region_to_new_spot() -> None:
    canvas_bytes = _busy_canvas_with_flat_patch((860, 1130, 1080, 1350))  # bottom-right flat
    assert pick_best_corner(canvas_bytes) == "bottom_right"


def test_stamp_with_backing_produces_valid_image_same_size() -> None:
    canvas_bytes = _busy_canvas_with_flat_patch((0, 0, 220, 220))
    logo_bytes = _solid_logo_bytes()
    stamped = stamp_brand_logo(canvas_bytes, logo_bytes, position="top_left", backing=True)
    out = Image.open(BytesIO(stamped))
    assert out.size == (1080, 1350)


def test_stamp_without_backing_is_backward_compatible() -> None:
    """The other in-flight caller (blue-card variant) uses the old signature
    with no `backing` kwarg at all — must keep working unchanged."""
    canvas_bytes = _busy_canvas_with_flat_patch((0, 0, 220, 220))
    logo_bytes = _solid_logo_bytes()
    stamped = stamp_brand_logo(canvas_bytes, logo_bytes, position="top_center", scale=0.15)
    out = Image.open(BytesIO(stamped))
    assert out.size == (1080, 1350)
