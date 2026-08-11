"""Content safety layer — post-generation risk signals (not prompt security)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from app.modules.content.domain.models import ContentSafetyResult, StructuredDraft

_DEFAULT = Path(__file__).resolve().parents[5] / "configs" / "content" / "generation"
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?")
_TRIVIAL = {"1", "2", "3", "4", "5", "10", "100", "0"}


class DefaultContentSafetyValidator:
    def __init__(self, config_dir: Path | None = None) -> None:
        path = (config_dir or _DEFAULT) / "safety.yaml"
        self._cfg: dict[str, Any] = {}
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                self._cfg = raw

    def validate(
        self, draft: StructuredDraft, *, source_text: str = ""
    ) -> ContentSafetyResult:
        text = f"{draft.hook}\n{draft.body}\n{draft.cta}".lower()
        reasons: list[str] = []
        sensitive = _has_any(text, self._cfg.get("sensitive_phrases") or [])
        legal = _has_any(text, self._cfg.get("legal_phrases") or [])
        compliance = _has_any(text, self._cfg.get("compliance_phrases") or [])
        unsafe = _has_any(text, self._cfg.get("unsafe_claim_phrases") or [])

        if sensitive:
            reasons.append("sensitive_language")
        if legal:
            reasons.append("legal_flags")
        if compliance:
            reasons.append("compliance_warnings")
        if unsafe:
            reasons.append("unsafe_claims")

        hallucination = False
        nums = {n for n in _NUMBER.findall(text) if n not in _TRIVIAL}
        if nums and source_text:
            src = set(_NUMBER.findall(source_text.lower()))
            flagged = [n for n in nums if n not in src]
            threshold = int(self._cfg.get("hallucination_number_threshold") or 1)
            if len(flagged) >= threshold:
                hallucination = True
                reasons.append(f"hallucination_risk: unverified numbers {', '.join(flagged[:3])}")

        score = 1.0
        if sensitive:
            score -= 0.35
        if legal:
            score -= 0.35
        if unsafe:
            score -= 0.3
        if compliance:
            score -= 0.2
        if hallucination:
            score -= 0.25
        score = max(0.0, round(score, 4))

        fail_sensitive = bool(self._cfg.get("fail_on_sensitive_language", True)) and sensitive
        fail_legal = bool(self._cfg.get("fail_on_legal_flags", True)) and legal
        fail_unsafe = bool(self._cfg.get("fail_on_unsafe_claims", True)) and unsafe
        fail_halluc = bool(self._cfg.get("fail_on_high_hallucination", True)) and hallucination
        safe = not (fail_sensitive or fail_legal or fail_unsafe or fail_halluc)

        return ContentSafetyResult(
            safe=safe,
            hallucination_risk=hallucination,
            unsafe_claims=unsafe,
            compliance_warnings=compliance,
            sensitive_language=sensitive,
            legal_flags=legal,
            reasons=tuple(reasons),
            score=score,
        )


def _has_any(text: str, phrases: list) -> bool:
    return any(str(p).lower() in text for p in phrases if p)
