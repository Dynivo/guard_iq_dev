"""Stamp the real Guard IQ logo onto generated creatives."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

_BRAND_DIR = Path(__file__).resolve().parents[4] / "assets" / "brand"
# Prefer transparent remove-bg mark; fall back to older asset.
_LOGO_CANDIDATES = (
    _BRAND_DIR / "image-removebg-preview.png",
    _BRAND_DIR / "guard_iq_logo.png",
)


def default_brand_logo_path() -> Path | None:
    for path in _LOGO_CANDIDATES:
        if path.is_file():
            return path
    return None


def default_brand_logo_bytes() -> bytes | None:
    """Bundled Guard IQ logo used when brand kit has no uploaded logo."""
    path = default_brand_logo_path()
    if path is None:
        return None
    return path.read_bytes()


def _knockout_light_background(logo: Image.Image, *, threshold: int = 248) -> Image.Image:
    """Make near-white logo canvas transparent so it sits cleanly on dark/light creatives."""
    rgba = logo.convert("RGBA")
    pixels = list(rgba.getdata())
    out = []
    for r, g, b, a in pixels:
        if a < 12:
            out.append((r, g, b, 0))
        elif r >= threshold and g >= threshold and b >= threshold:
            out.append((r, g, b, 0))
        else:
            out.append((r, g, b, a))
    rgba.putdata(out)
    return rgba


def prepare_logo(logo_bytes: bytes, *, max_side: int) -> Image.Image:
    logo = _knockout_light_background(Image.open(BytesIO(logo_bytes)))
    logo.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return logo


def stamp_brand_logo(
    image_bytes: bytes,
    logo_bytes: bytes,
    *,
    position: str = "top_center",
    scale: float = 0.12,
) -> bytes:
    """Composite logo onto PNG bytes. position: top_center | bottom_right | bottom_left."""
    canvas = Image.open(BytesIO(image_bytes)).convert("RGBA")
    side = max(64, int(min(canvas.width, canvas.height) * scale))
    logo = prepare_logo(logo_bytes, max_side=side)

    margin = int(min(canvas.width, canvas.height) * 0.045)
    pos = (position or "top_center").strip().lower()
    if pos == "bottom_right":
        lx = canvas.width - logo.width - margin
        ly = canvas.height - logo.height - margin
    elif pos == "bottom_left":
        lx = margin
        ly = canvas.height - logo.height - margin
    else:
        lx = (canvas.width - logo.width) // 2
        ly = margin

    canvas.alpha_composite(logo, dest=(lx, ly))
    buf = BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
