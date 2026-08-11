"""Parse candidate text into canonical LinkedIn post sections."""

from __future__ import annotations

import json
import re
from typing import Any

SECTION_KEYS = ("hook", "body", "cta", "hashtags", "statistics", "visual_prompt")

_HASHTAG_RE = re.compile(r"#\w+")


def parse_sections(text: str) -> dict[str, Any]:
    """Parse JSON or raw text into a sections dict.

    Always returns keys: hook, body, cta, hashtags (list), statistics, visual_prompt.
    Tolerant of markdown fences, partial JSON, and plain prose.
    """
    empty = _empty_sections()
    raw = (text or "").strip()
    if not raw:
        return empty

    data = try_parse_json(raw)
    if data is not None:
        return _from_mapping(data, fallback_text=raw)

    return _from_raw_text(raw)


def try_parse_json(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from raw/fenced text when possible."""
    return _try_json(text)


def normalize_hashtags(value: Any) -> list[str]:
    """Normalize hashtag lists/strings to a `#tag` list."""
    return _normalize_hashtags(value)


def _empty_sections() -> dict[str, Any]:
    return {
        "hook": "",
        "body": "",
        "cta": "",
        "hashtags": [],
        "statistics": "",
        "visual_prompt": "",
    }


def _try_json(text: str) -> dict[str, Any] | None:
    blob = text
    if "```" in blob:
        match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.DOTALL | re.IGNORECASE
        )
        if match:
            blob = match.group(1)
    start = blob.find("{")
    end = blob.rfind("}")
    if start < 0 or end <= start:
        return None
    blob = blob[start : end + 1]
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_hashtags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        tags: list[str] = []
        for item in value:
            s = str(item).strip()
            if not s:
                continue
            if not s.startswith("#"):
                s = f"#{s.lstrip('#')}"
            tags.append(s)
        return tags
    if isinstance(value, str):
        parts = value.replace(",", " ").split()
        tags = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if not part.startswith("#"):
                part = f"#{part.lstrip('#')}"
            tags.append(part)
        if tags:
            return tags
        return _HASHTAG_RE.findall(value)
    return []


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _from_mapping(data: dict[str, Any], *, fallback_text: str) -> dict[str, Any]:
    nested = data.get("sections")
    source = data
    if isinstance(nested, dict):
        source = {**data, **nested}

    hook = _as_str(source.get("hook"))
    body = _as_str(source.get("body") or source.get("text") or source.get("content"))
    cta = _as_str(source.get("cta") or source.get("call_to_action"))
    hashtags = _normalize_hashtags(source.get("hashtags") or source.get("tags"))
    statistics = _as_str(source.get("statistics") or source.get("stats"))
    visual_prompt = _as_str(
        source.get("visual_prompt")
        or source.get("image_prompt")
        or source.get("visualPrompt")
    )

    if not body and not hook:
        body = fallback_text

    return {
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": hashtags,
        "statistics": statistics,
        "visual_prompt": visual_prompt,
    }


def _from_raw_text(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    hook = ""
    body = text
    cta = ""
    tags: list[str] = []
    statistics = ""
    visual_prompt = ""

    if lines:
        first = lines[0].lstrip("# ").strip()
        hook = first[:500]
        body = "\n".join(lines[1:]).strip() or text

    for line in lines:
        low = line.lower().strip()
        if low.startswith("cta:") or low.startswith("call to action:"):
            cta = line.split(":", 1)[-1].strip()
        elif low.startswith("statistics:") or low.startswith("stats:"):
            statistics = line.split(":", 1)[-1].strip()
        elif low.startswith("visual_prompt:") or low.startswith("image_prompt:"):
            visual_prompt = line.split(":", 1)[-1].strip()
        if "#" in line and not line.startswith("# "):
            tags.extend(_HASHTAG_RE.findall(line))

    # de-dupe hashtags preserving order
    seen: set[str] = set()
    unique_tags: list[str] = []
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_tags.append(tag)

    return {
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": unique_tags,
        "statistics": statistics,
        "visual_prompt": visual_prompt,
    }


def sections_to_json_text(sections: dict[str, Any]) -> str:
    """Serialize sections to stable JSON text for merge output."""
    payload = {
        "hook": str(sections.get("hook") or ""),
        "body": str(sections.get("body") or ""),
        "cta": str(sections.get("cta") or ""),
        "hashtags": list(sections.get("hashtags") or []),
        "statistics": str(sections.get("statistics") or ""),
        "visual_prompt": str(sections.get("visual_prompt") or ""),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def section_text(sections: dict[str, Any], key: str) -> str:
    """Flatten a section value to comparable text."""
    value = sections.get(key)
    if key == "hashtags":
        if isinstance(value, list):
            return " ".join(str(v) for v in value)
        return str(value or "")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")
