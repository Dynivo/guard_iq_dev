"""Article normalizer + language detection + validators."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.modules.news.application.category_utils import normalize_category
from app.modules.news.domain.models import CanonicalArticle, NormalizedArticle, SourceDefinition


_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}


class DefaultLanguageDetector:
    def detect(self, text: str) -> str:
        sample = (text or "")[:800].lower()
        if not sample.strip():
            return "en"
        # Lightweight heuristic — replaceable with a real detector later
        if re.search(r"\b(the|and|with|from|that)\b", sample):
            return "en"
        if re.search(r"\b(le|la|les|des|une)\b", sample):
            return "fr"
        if re.search(r"\b(der|die|das|und|mit)\b", sample):
            return "de"
        return "en"


class DefaultFeedValidator:
    def validate_items(
        self, items: list[NormalizedArticle]
    ) -> tuple[list[NormalizedArticle], list[str]]:
        ok: list[NormalizedArticle] = []
        errors: list[str] = []
        for i, item in enumerate(items):
            if not (item.title or "").strip():
                errors.append(f"item[{i}]: missing title")
                continue
            if not (item.url or "").strip():
                errors.append(f"item[{i}]: missing url")
                continue
            ok.append(item)
        return ok, errors


class DefaultContentValidator:
    def validate(self, article: CanonicalArticle) -> tuple[bool, str]:
        if not article.title.strip():
            return False, "missing title"
        if not article.url.strip():
            return False, "missing url"
        if len(article.title) > 1000:
            return False, "title too long"
        return True, ""


def canonicalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") or "/"
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING
    ]
    query = urlencode(sorted(query_pairs))
    return urlunparse((scheme, netloc, path, "", query, ""))


def content_hash(title: str, summary: str, body: str) -> str:
    blob = f"{title.strip().lower()}\n{(summary or '').strip().lower()}\n{(body or '')[:2000].strip().lower()}"
    return hashlib.sha256(blob.encode()).hexdigest()


class DefaultNormalizer:
    def __init__(self, language_detector: DefaultLanguageDetector | None = None) -> None:
        self._lang = language_detector or DefaultLanguageDetector()

    def normalize(
        self,
        raw: NormalizedArticle | dict[str, Any],
        *,
        source: SourceDefinition | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> CanonicalArticle:
        if isinstance(raw, dict):
            title = str(raw.get("title") or "")
            url = str(raw.get("url") or "")
            summary = str(raw.get("summary") or "")
            body = str(raw.get("body_text") or raw.get("body") or "")
            author = str(raw.get("author") or "")
            published = raw.get("published_at")
            if isinstance(published, str):
                try:
                    published = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except ValueError:
                    published = None
            payload = dict(raw.get("raw_payload") or raw)
            images = tuple(str(x) for x in (raw.get("images") or []))
            tags = tuple(str(x) for x in (raw.get("tags") or []))
            category = normalize_category(raw.get("category"))
        else:
            title = raw.title or ""
            url = raw.url or ""
            summary = raw.summary or ""
            body = raw.body_text or ""
            author = raw.author or ""
            published = raw.published_at
            payload = dict(raw.raw_payload or {})
            images = tuple(str(x) for x in (payload.get("images") or []))
            tags = tuple(str(x) for x in (payload.get("tags") or []))
            category = normalize_category(payload.get("category") or getattr(raw, "category", ""))

        canon = canonicalize_url(url)
        text_for_lang = f"{title} {summary} {body}"
        lang = self._lang.detect(text_for_lang)
        return CanonicalArticle(
            title=title.strip(),
            url=url.strip(),
            canonical_url=canon or url.strip(),
            summary=summary.strip(),
            body_text=body.strip(),
            author=author.strip(),
            source=(source.name if source else "") or str(payload.get("source") or ""),
            category=category,
            tags=tags,
            language=lang,
            published_at=published if isinstance(published, datetime) else None,
            updated_at=datetime.now(timezone.utc),
            images=images,
            organization_id=organization_id,
            content_hash=content_hash(title, summary, body),
            metadata={
                "connector_type": source.connector_type if source else "",
                "source_id": source.source_id if source else "",
            },
            raw_payload=payload,
        )
