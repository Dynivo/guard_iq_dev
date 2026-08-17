"""Stamp the real Guard IQ logo onto generated creatives."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat

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


def _corner_origin(
    position: str, canvas_size: tuple[int, int], logo_size: tuple[int, int], margin: int
) -> tuple[int, int]:
    cw, ch = canvas_size
    lw, lh = logo_size
    pos = (position or "top_center").strip().lower()
    if pos == "bottom_right":
        return cw - lw - margin, ch - lh - margin
    if pos == "bottom_left":
        return margin, ch - lh - margin
    if pos == "bottom_center":
        return (cw - lw) // 2, ch - lh - margin
    if pos == "top_left":
        return margin, margin
    if pos == "top_right":
        return cw - lw - margin, margin
    return (cw - lw) // 2, margin  # top_center + unrecognized fallback


_CORNER_CANDIDATES = (
    "top_left",
    "top_center",
    "top_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
)


def pick_best_corner(
    image_bytes: bytes,
    *,
    scale: float = 0.11,
    candidates: tuple[str, ...] = _CORNER_CANDIDATES,
) -> str:
    """Content-aware placement: sample each candidate region's local visual
    "busyness" (grayscale standard deviation) and return the flattest one —
    the spot a logo will sit cleanest against, instead of a fixed corner
    regardless of what the generated image actually looks like there."""
    canvas = Image.open(BytesIO(image_bytes)).convert("RGB")
    side = max(64, int(min(canvas.width, canvas.height) * scale))
    margin = int(min(canvas.width, canvas.height) * 0.045)
    pad = int(side * 0.18)

    best_position = candidates[0]
    best_variance = None
    for position in candidates:
        lx, ly = _corner_origin(position, (canvas.width, canvas.height), (side, side), margin)
        box = (
            max(0, lx - pad),
            max(0, ly - pad),
            min(canvas.width, lx + side + pad),
            min(canvas.height, ly + side + pad),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        region = canvas.crop(box).convert("L")
        variance = ImageStat.Stat(region).stddev[0]
        if best_variance is None or variance < best_variance:
            best_variance = variance
            best_position = position
    return best_position


def _rounded_rect_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


def _backing_plate(size: tuple[int, int], *, opacity: int = 235) -> Image.Image:
    """A soft rounded near-white plate behind the logo, so it reads cleanly
    against any background instead of depending on the AI having left that
    exact spot blank."""
    radius = int(min(size) * 0.22)
    mask = _rounded_rect_mask(size, radius)
    plate = Image.new("RGBA", size, (255, 255, 255, 0))
    solid = Image.new("RGBA", size, (255, 255, 255, opacity))
    plate.paste(solid, (0, 0), mask)
    return plate


def stamp_brand_logo(
    image_bytes: bytes,
    logo_bytes: bytes,
    *,
    position: str = "top_center",
    scale: float = 0.12,
    backing: bool = False,
) -> bytes:
    """Composite logo onto PNG bytes.

    position: top_left | top_center | top_right | bottom_left | bottom_center
    | bottom_right (unrecognized values fall back to top_center).

    backing: when True, draws a soft rounded near-white plate behind the logo
    first, so contrast/legibility holds regardless of what's underneath —
    use this instead of relying on a prompt instruction to leave that area
    blank, which drifts from the compositor's exact pixel math.
    """
    canvas = Image.open(BytesIO(image_bytes)).convert("RGBA")
    side = max(64, int(min(canvas.width, canvas.height) * scale))
    logo = prepare_logo(logo_bytes, max_side=side)

    margin = int(min(canvas.width, canvas.height) * 0.045)
    lx, ly = _corner_origin(position, (canvas.width, canvas.height), logo.size, margin)

    if backing:
        pad = int(max(logo.size) * 0.18)
        plate_size = (logo.width + 2 * pad, logo.height + 2 * pad)
        plate = _backing_plate(plate_size)
        plate_origin = (lx - pad, ly - pad)
        canvas.alpha_composite(plate, dest=plate_origin)

    canvas.alpha_composite(logo, dest=(lx, ly))
    buf = BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
