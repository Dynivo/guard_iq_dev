"""Deduplication — URL, content hash, title similarity."""

from __future__ import annotations

import re
import uuid
from difflib import SequenceMatcher

from app.modules.news.application.normalizer import canonicalize_url
from app.modules.news.domain.models import CanonicalArticle


def _normalize_title(title: str) -> str:
    t = re.sub(r"[^a-z0-9\s]", "", (title or "").lower())
    return " ".join(t.split())


class InMemoryDeduplicator:
    """URL + content-hash seen set (unit/tests and memory pipeline)."""

    def __init__(self) -> None:
        self._urls: set[str] = set()
        self._hashes: set[str] = set()

    async def is_duplicate(
        self, org_id: uuid.UUID, url: str, content_hash: str | None = None
    ) -> bool:
        key = f"{org_id}:{canonicalize_url(url) or url}"
        if key in self._urls:
            return True
        if content_hash and f"{org_id}:{content_hash}" in self._hashes:
            return True
        return False

    async def mark_seen(self, org_id: uuid.UUID, url: str) -> None:
        self._urls.add(f"{org_id}:{canonicalize_url(url) or url}")

    def mark_hash(self, org_id: uuid.UUID, content_hash: str) -> None:
        if content_hash:
            self._hashes.add(f"{org_id}:{content_hash}")

    def is_near_duplicate(
        self, left: CanonicalArticle, right: CanonicalArticle, *, threshold: float
    ) -> bool:
        if left.canonical_url and left.canonical_url == right.canonical_url:
            return True
        if left.content_hash and left.content_hash == right.content_hash:
            return True
        a = _normalize_title(left.title)
        b = _normalize_title(right.title)
        if not a or not b:
            return False
        return SequenceMatcher(None, a, b).ratio() >= threshold


class DefaultDuplicateDetector:
    """Title / hash / URL similarity without persistence."""

    def is_near_duplicate(
        self, left: CanonicalArticle, right: CanonicalArticle, *, threshold: float
    ) -> bool:
        return InMemoryDeduplicator().is_near_duplicate(
            left, right, threshold=threshold
        )
