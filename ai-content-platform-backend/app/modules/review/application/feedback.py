"""Feedback engine — structured reason codes and categories."""

from __future__ import annotations

from app.modules.review.application.config_loader import load_review_config
from app.modules.review.domain.models import FeedbackCategory


class FeedbackEngine:
    def __init__(self, config_dir: str | None = None) -> None:
        self._config = load_review_config(config_dir)

    def _allowed_categories(self) -> set[str]:
        rc = self._config.get("reason_codes") or {}
        cats = rc.get("categories") or [c.value for c in FeedbackCategory]
        return {str(c) for c in cats}

    def _codes_for_category(self, category: str) -> set[str]:
        rc = self._config.get("reason_codes") or {}
        codes = (rc.get("reason_codes") or {}).get(category) or []
        return {str(c) for c in codes}

    def normalize_category(self, category: str) -> str:
        c = (category or "general").strip().lower()
        if c in self._allowed_categories():
            return c
        aliases = {"style": "writing", "copy": "writing", "image": "visual"}
        return aliases.get(c, "general")

    def validate_reason_codes(
        self, codes: list[str], categories: list[str]
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        allowed_cats = self._allowed_categories()
        for cat in categories:
            if cat not in allowed_cats:
                errors.append(f"unknown_category:{cat}")
        if not codes:
            return (len(errors) == 0, errors)
        valid_codes: set[str] = set()
        for cat in categories or list(allowed_cats):
            valid_codes |= self._codes_for_category(cat)
        for code in codes:
            if code not in valid_codes and valid_codes:
                errors.append(f"unknown_reason_code:{code}")
        return (len(errors) == 0, errors)

    def template(self, key: str) -> dict[str, str]:
        templates = (self._config.get("templates") or {}).get("templates") or {}
        raw = templates.get(key) or {}
        return {"title": str(raw.get("title") or key), "body": str(raw.get("body") or "")}
