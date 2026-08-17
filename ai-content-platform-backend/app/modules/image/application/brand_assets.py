"""Bundled brand assets used as Gemini generation references.

Separate from logo_stamp.py: that module loads the logo for deterministic
post-generation compositing, whereas this one loads the *house style*
exemplar that gets sent to the model as a visual reference so generated
creatives match an approved look instead of drifting per prompt wording.
"""

from __future__ import annotations

from pathlib import Path

_BRAND_DIR = Path(__file__).resolve().parents[4] / "assets" / "brand"

# First match wins. Drop an approved creative here to set the house style.
_STYLE_REFERENCE_CANDIDATES = (
    "style_reference.png",
    "style_reference.jpg",
    "style_reference.jpeg",
    "style_reference.webp",
)

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def default_style_reference_path() -> Path | None:
    for name in _STYLE_REFERENCE_CANDIDATES:
        path = _BRAND_DIR / name
        if path.is_file():
            return path
    return None


def default_style_reference() -> tuple[bytes, str] | None:
    """(bytes, mime_type) for the bundled house-style exemplar, or None when
    no style reference is bundled — in which case generation proceeds on the
    text prompt alone, exactly as before."""
    path = default_style_reference_path()
    if path is None:
        return None
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")
    try:
        return path.read_bytes(), mime
    except OSError:
        return None
