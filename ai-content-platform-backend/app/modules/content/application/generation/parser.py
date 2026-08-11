"""Output parser — Raw AI → StructuredDraft candidate (never exposed raw)."""

from __future__ import annotations

import json
import re

from app.modules.content.domain.models import (
    ContentFormat,
    DraftSlide,
    RawAIOutput,
    StructuredDraft,
)


class DefaultOutputParser:
    def parse(
        self, raw: RawAIOutput, *, content_type: str = "", format: str = ""
    ) -> StructuredDraft:
        text = (raw.text or "").strip()
        if not text:
            return StructuredDraft(content_type=content_type, format=format or ContentFormat.SINGLE.value)

        parsed = _try_json(text)
        if parsed is not None:
            return _from_mapping(parsed, content_type=content_type, format=format, raw=raw)

        if format == ContentFormat.CAROUSEL.value or "slide" in text.lower():
            slides = _parse_markdown_slides(text)
            if slides:
                return StructuredDraft(
                    hook=slides[0].title,
                    body="\n\n".join(f"{s.title}\n{s.body}".strip() for s in slides),
                    slides=slides,
                    format=ContentFormat.CAROUSEL.value,
                    content_type=content_type or "carousel",
                    provider_metadata={"provider": raw.provider, "model": raw.model},
                    markdown=text,
                )

        hook, body, cta, tags = _parse_markdown_sections(text)
        return StructuredDraft(
            hook=hook,
            body=body or text,
            cta=cta,
            hashtags=tags,
            format=format or ContentFormat.SINGLE.value,
            content_type=content_type or "single_post",
            provider_metadata={"provider": raw.provider, "model": raw.model},
            markdown=text,
        )


def _try_json(text: str) -> dict | None:
    blob = text
    if "```" in blob:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.DOTALL | re.IGNORECASE)
        if m:
            blob = m.group(1)
    start = blob.find("{")
    end = blob.rfind("}")
    if start >= 0 and end > start:
        blob = blob[start : end + 1]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _from_mapping(
    data: dict, *, content_type: str, format: str, raw: RawAIOutput
) -> StructuredDraft:
    slides_raw = data.get("slides") or []
    slides = tuple(
        DraftSlide(
            index=int(s.get("index", i + 1)),
            title=str(s.get("title") or ""),
            body=str(s.get("body") or s.get("text") or ""),
        )
        for i, s in enumerate(slides_raw)
        if isinstance(s, dict)
    )
    fmt = format or (
        ContentFormat.CAROUSEL.value if slides else ContentFormat.SINGLE.value
    )
    hashtags = data.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split() if h.strip()]
    return StructuredDraft(
        hook=str(data.get("hook") or ""),
        body=str(data.get("body") or data.get("text") or ""),
        cta=str(data.get("cta") or ""),
        hashtags=tuple(str(h) for h in hashtags),
        sections={k: str(v) for k, v in (data.get("sections") or {}).items()},
        slides=slides,
        format=fmt,
        content_type=content_type or str(data.get("content_type") or "single_post"),
        provider_metadata={"provider": raw.provider, "model": raw.model},
        metadata={"parsed_from": "json"},
    )


def _parse_markdown_sections(text: str) -> tuple[str, str, str, tuple[str, ...]]:
    hook = ""
    body = text
    cta = ""
    tags: list[str] = []
    lines = text.splitlines()
    if lines:
        hook = lines[0].lstrip("# ").strip()
        body = "\n".join(lines[1:]).strip() or text
    for line in lines:
        low = line.lower()
        if low.startswith("cta:") or low.startswith("call to action:"):
            cta = line.split(":", 1)[-1].strip()
        if "#" in line and not line.startswith("# "):
            tags.extend(re.findall(r"#\w+", line))
    return hook[:500], body, cta, tuple(tags)


def _parse_markdown_slides(text: str) -> tuple[DraftSlide, ...]:
    parts = re.split(r"(?m)^(?:#{1,3}\s*|Slide\s+\d+[:.\s-]*)", text)
    slides: list[DraftSlide] = []
    idx = 1
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        slides.append(DraftSlide(index=idx, title=title, body=body))
        idx += 1
    return tuple(slides)
