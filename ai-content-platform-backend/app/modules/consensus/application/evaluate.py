"""Deterministic candidate evaluation — no LLM calls."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from app.modules.consensus.application.config_loader import load_consensus_config
from app.modules.consensus.application import sections as section_parser
from app.modules.consensus.domain.models import CandidateResponse, EvaluationScore

_SLANG = frozenset(
    {
        "lol",
        "lmao",
        "omg",
        "tbh",
        "imo",
        "imho",
        "wtf",
        "smh",
        "yo",
        "dude",
        "gonna",
        "wanna",
        "gotta",
        "ain't",
        "clickbait",
    }
)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U00002700-\U000027BF"
    "\U0001F600-\U0001F64F"
    "]+",
    flags=re.UNICODE,
)
_NUMBER_RE = re.compile(r"\b\d+(\.\d+)?%?\b")
_CITATION_RE = re.compile(r"https?://|\[\d+\]|\bsource\b|\bcite[sd]?\b", re.I)
_LINKEDIN_MARKERS = ("\n\n", "•", "-", "—", "#")

_BRAND_PATH = (
    Path(__file__).resolve().parents[4] / "configs" / "content" / "generation" / "brand.yaml"
)


class DefaultDeterministicEvaluator:
    """Score candidates using configs/consensus/evaluation.yaml metrics."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config if config is not None else load_consensus_config()
        evaluation = cfg.get("evaluation") or {}
        self._metrics = dict(evaluation.get("metrics") or {})
        self._thresholds = dict(evaluation.get("thresholds") or {})
        self._brand_keywords = self._load_brand_keywords()

    def evaluate(self, candidate: CandidateResponse) -> EvaluationScore:
        secs = candidate.sections or section_parser.parse_sections(candidate.text)
        scores: dict[str, float] = {}
        details: dict[str, Any] = {}

        scores["json_validity"] = self._json_validity(candidate.text, details)
        scores["structure"] = self._structure(secs, details)
        scores["length"] = self._length(candidate.text or secs.get("body") or "", details)
        scores["hook"] = self._hook(secs, details)
        scores["cta"] = self._cta(secs, details)
        scores["hashtags"] = self._hashtags(secs, details)
        scores["readability"] = self._readability(
            str(secs.get("body") or candidate.text or ""), details
        )
        scores["enterprise_tone"] = self._enterprise_tone(
            candidate.text or "", details
        )
        scores["linkedin_style"] = self._linkedin_style(secs, candidate.text or "", details)
        scores["brand_keywords"] = self._brand_keywords_score(
            candidate.text or "", details
        )
        scores["evidence"] = self._evidence(candidate.text or "", details)
        scores["professionalism"] = self._professionalism(candidate.text or "", details)

        # Also expose YAML aliases for reporting
        scores["hook_quality"] = scores["hook"]
        scores["cta_quality"] = scores["cta"]

        composite = self._composite(scores)
        min_composite = float(self._thresholds.get("min_composite", 0.35))
        pass_composite = float(self._thresholds.get("pass_composite", 0.55))
        passed = composite >= pass_composite and scores["json_validity"] >= 0.5
        if composite < min_composite:
            passed = False

        return EvaluationScore(
            candidate_id=candidate.candidate_id,
            scores=scores,
            composite=round(composite, 4),
            passed=passed,
            details=details,
        )

    def evaluate_many(self, candidates: list[CandidateResponse]) -> list[EvaluationScore]:
        return [self.evaluate(c) for c in candidates]

    def _metric_cfg(self, *names: str) -> dict[str, Any]:
        for name in names:
            cfg = self._metrics.get(name)
            if isinstance(cfg, dict):
                return cfg
        return {}

    def _weight(self, *names: str) -> float:
        cfg = self._metric_cfg(*names)
        try:
            return float(cfg.get("weight", 0.0))
        except (TypeError, ValueError):
            return 0.0

    def _composite(self, scores: dict[str, float]) -> float:
        # Prefer primary metric names used by evaluation.yaml
        pairs = [
            ("json_validity", "json_validity"),
            ("structure", "structure"),
            ("length", "length"),
            ("hook_quality", "hook"),
            ("cta_quality", "cta"),
            ("hashtags", "hashtags"),
            ("readability", "readability"),
            ("enterprise_tone", "enterprise_tone"),
            ("linkedin_style", "linkedin_style"),
            ("brand_keywords", "brand_keywords"),
            ("evidence", "evidence"),
            ("professionalism", "professionalism"),
        ]
        total_w = 0.0
        total = 0.0
        for yaml_name, score_key in pairs:
            w = self._weight(yaml_name, score_key)
            if w <= 0:
                continue
            total_w += w
            total += w * float(scores.get(score_key, 0.0))
        if total_w <= 0:
            vals = [scores[k] for k in ("json_validity", "structure", "hook", "cta") if k in scores]
            return sum(vals) / len(vals) if vals else 0.0
        return total / total_w

    def _json_validity(self, text: str, details: dict[str, Any]) -> float:
        parsed = section_parser.try_parse_json(text)
        details["json_valid"] = parsed is not None
        if parsed is None:
            return 0.2 if (text or "").strip() else 0.0
        return 1.0

    def _structure(self, secs: dict[str, Any], details: dict[str, Any]) -> float:
        required = ("hook", "body", "cta", "hashtags")
        present = 0
        for key in required:
            val = secs.get(key)
            if key == "hashtags":
                ok = isinstance(val, list) and len(val) > 0
            else:
                ok = bool(str(val or "").strip())
            if ok:
                present += 1
        details["structure_present"] = present
        return present / len(required)

    def _length(self, text: str, details: dict[str, Any]) -> float:
        cfg = self._metric_cfg("length")
        min_c = int(cfg.get("min_chars", 80))
        max_c = int(cfg.get("max_chars", 3000))
        n = len(text.strip())
        details["char_count"] = n
        if n <= 0:
            return 0.0
        if min_c <= n <= max_c:
            return 1.0
        if n < min_c:
            return max(0.0, n / min_c)
        # Soft penalty above max
        over = n - max_c
        return max(0.0, 1.0 - over / max_c)

    def _hook(self, secs: dict[str, Any], details: dict[str, Any]) -> float:
        cfg = self._metric_cfg("hook_quality", "hook")
        hook = str(secs.get("hook") or "").strip()
        details["hook_chars"] = len(hook)
        if not hook:
            return 0.0
        min_h = int(cfg.get("min_hook_chars", 20))
        max_h = int(cfg.get("max_hook_chars", 220))
        n = len(hook)
        if n < min_h:
            return max(0.1, n / min_h)
        if n > max_h:
            return max(0.3, 1.0 - (n - max_h) / max_h)
        score = 0.7
        if hook[0].isupper():
            score += 0.15
        if not hook.isupper():
            score += 0.15
        return min(1.0, score)

    def _cta(self, secs: dict[str, Any], details: dict[str, Any]) -> float:
        cfg = self._metric_cfg("cta_quality", "cta")
        cta = str(secs.get("cta") or "").strip()
        details["cta_chars"] = len(cta)
        if not cta:
            return 0.0
        min_c = int(cfg.get("min_cta_chars", 10))
        if len(cta) < min_c:
            return max(0.1, len(cta) / min_c)
        verbs = ("share", "comment", "discuss", "learn", "read", "join", "follow", "tell")
        bonus = 0.2 if any(v in cta.lower() for v in verbs) else 0.0
        return min(1.0, 0.8 + bonus)

    def _hashtags(self, secs: dict[str, Any], details: dict[str, Any]) -> float:
        cfg = self._metric_cfg("hashtags")
        tags = secs.get("hashtags") or []
        if isinstance(tags, str):
            tags = section_parser.normalize_hashtags(tags)
        count = len(tags) if isinstance(tags, list) else 0
        details["hashtag_count"] = count
        min_c = int(cfg.get("min_count", 1))
        max_c = int(cfg.get("max_count", 8))
        if count < min_c:
            return 0.0 if count == 0 else 0.4
        if count > max_c:
            return max(0.2, 1.0 - (count - max_c) * 0.15)
        return 1.0

    def _readability(self, text: str, details: dict[str, Any]) -> float:
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        if not sentences:
            details["avg_sentence_len"] = 0
            return 0.0
        words = [w for w in re.findall(r"\b\w+\b", text)]
        avg = len(words) / max(len(sentences), 1)
        details["avg_sentence_len"] = round(avg, 2)
        # Ideal LinkedIn sentence ~12–22 words
        if 12 <= avg <= 22:
            return 1.0
        if avg < 12:
            return max(0.3, avg / 12)
        # Penalize long sentences
        return max(0.2, 1.0 - (avg - 22) / 40)

    def _enterprise_tone(self, text: str, details: dict[str, Any]) -> float:
        lower = text.lower()
        words = re.findall(r"\b\w+\b", lower)
        slang_hits = sum(1 for w in words if w in _SLANG)
        emoji_hits = len(_EMOJI_RE.findall(text))
        details["slang_hits"] = slang_hits
        details["emoji_hits"] = emoji_hits
        score = 1.0
        score -= min(0.6, slang_hits * 0.15)
        score -= min(0.4, emoji_hits * 0.1)
        if text and text.upper() == text and len(text) > 20:
            score -= 0.3
        return max(0.0, score)

    def _linkedin_style(
        self, secs: dict[str, Any], text: str, details: dict[str, Any]
    ) -> float:
        score = 0.4
        if str(secs.get("hook") or "").strip():
            score += 0.2
        if str(secs.get("cta") or "").strip():
            score += 0.15
        tags = secs.get("hashtags") or []
        if isinstance(tags, list) and tags:
            score += 0.1
        if any(m in text for m in _LINKEDIN_MARKERS):
            score += 0.15
        details["linkedin_style_score"] = round(min(1.0, score), 3)
        return min(1.0, score)

    def _brand_keywords_score(self, text: str, details: dict[str, Any]) -> float:
        if not self._brand_keywords:
            details["brand_hits"] = 0
            return 0.5
        lower = text.lower()
        hits = [kw for kw in self._brand_keywords if kw.lower() in lower]
        details["brand_hits"] = len(hits)
        if not hits:
            return 0.35
        return min(1.0, 0.5 + 0.15 * len(hits))

    def _evidence(self, text: str, details: dict[str, Any]) -> float:
        numbers = _NUMBER_RE.findall(text)
        citations = _CITATION_RE.findall(text)
        details["number_markers"] = len(numbers)
        details["citation_markers"] = len(citations)
        if not numbers and not citations:
            return 0.25
        return min(1.0, 0.4 + 0.15 * len(numbers) + 0.2 * len(citations))

    def _professionalism(self, text: str, details: dict[str, Any]) -> float:
        if not text.strip():
            return 0.0
        score = 0.7
        if _EMOJI_RE.search(text):
            score -= 0.15
        if "!!!" in text or "???" in text:
            score -= 0.15
        if re.search(r"\b(guaranteed|miracle|secret hack)\b", text, re.I):
            score -= 0.25
        # Prefer complete sentences
        if text.strip()[-1:] in ".!?":
            score += 0.1
        details["professionalism_raw"] = round(score, 3)
        return max(0.0, min(1.0, score))

    @staticmethod
    def _load_brand_keywords() -> list[str]:
        if not _BRAND_PATH.exists():
            return []
        try:
            raw = yaml.safe_load(_BRAND_PATH.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return []
        vocab = raw.get("preferred_vocabulary") or []
        return [str(v) for v in vocab if v]
