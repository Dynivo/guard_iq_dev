"""Helpers for normalizing news article fields from heterogeneous connectors."""

from __future__ import annotations

from typing import Any


def normalize_category(value: Any) -> str:
    """Coerce connector category values into a single clean label.

    NewsData often returns ``["technology", "top"]``; RSS may return a string.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return parts[0] if parts else ""
    if isinstance(value, tuple):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return parts[0] if parts else ""
    text = str(value).strip()
    if not text:
        return ""
    # Recover from previously stringified lists: "['technology', 'top']"
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].replace("'", "").replace('"', "")
        parts = [p.strip() for p in inner.split(",") if p.strip()]
        return parts[0] if parts else ""
    return text
