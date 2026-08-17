"""Post-generation text-accuracy check via OpenAI vision.

Catches rendered typos (e.g. "exposoed") and fabricated on-image text (e.g. an
invented "CONSULTING" subtitle) that the pixel-only DefaultImageValidator can't
see — it has no OCR/vision capability at all.

Best-effort: any failure (no key, network error, bad JSON) reports passed=True
so a broken checker never blocks image generation — same pattern as the other
AI-assisted helpers in content_subject.py.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_MODEL = "gpt-4o-mini"


@dataclass(slots=True)
class TextAccuracyResult:
    checked: bool
    passed: bool
    issues: tuple[str, ...] = ()


async def check_rendered_text(
    image_bytes: bytes,
    card_copy: dict[str, Any],
    *,
    api_key: str | None = None,
    client: AsyncOpenAI | None = None,
) -> TextAccuracyResult:
    copy_lines = "\n".join(
        f"{k}: {v}" for k, v in (card_copy or {}).items() if v and k != "brand_name"
    )
    if not copy_lines.strip():
        return TextAccuracyResult(checked=False, passed=True)

    settings = get_settings()
    key = (api_key if api_key is not None else settings.OPENAI_API_KEY).strip()
    if not key and client is None:
        return TextAccuracyResult(checked=False, passed=True)

    b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "Read every piece of text rendered in this image. Compare it against the "
        "INTENDED copy below (this is what the text was supposed to say). Report "
        "any misspelled words, garbled letters, or rendered text that clearly "
        "diverges from the intended copy. Ignore minor rewording or line-wrapping "
        "— only flag actual spelling/character errors, or fabricated text that "
        "isn't in the intended copy at all (e.g. an invented tagline nobody asked "
        "for).\n\n"
        f"INTENDED COPY:\n{copy_lines}\n\n"
        'Respond with ONLY JSON: {"text_ok": true|false, "issues": ["short description", ...]}'
    )
    try:
        oc = client or AsyncOpenAI(api_key=key)
        result = await oc.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        data = json.loads(result.choices[0].message.content or "{}")
        issues = tuple(str(i) for i in (data.get("issues") or []))[:8]
        passed = bool(data.get("text_ok", True)) and not issues
        return TextAccuracyResult(checked=True, passed=passed, issues=issues)
    except Exception as exc:  # noqa: BLE001 — best-effort, never block generation
        logger.warning("Text-accuracy check failed, treating as passed: %s", exc)
        return TextAccuracyResult(checked=False, passed=True)
