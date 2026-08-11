"""VisualPatternEngine — choose a LinkedIn design pattern before prompt build."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.image.application.config_loader import load_yaml


class VisualPatternEngine:
    """Selects a pattern from YAML library using intent + legacy mode + message cues."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._patterns = load_yaml("visual_patterns.yaml", config_dir)
        self._intents = load_yaml("post_intent_patterns.yaml", config_dir)

    def detect_intent(
        self,
        *,
        hook: str,
        body: str,
        content_type: str = "",
        message: dict[str, Any] | None = None,
    ) -> str:
        ctype = (content_type or "").strip().lower()
        intent_keys = set((self._intents.get("intents") or {}).keys())
        if ctype in intent_keys:
            # Map platform content_type into planning intent when direct match
            if ctype in {"educational", "success_story", "personal_achievement"}:
                if ctype == "personal_achievement":
                    return "personal"
                return ctype
        blob = f"{hook} {body}".lower()
        for rule in self._intents.get("keyword_intent") or []:
            if not isinstance(rule, dict):
                continue
            kws = rule.get("keywords") or []
            if any(str(k).lower() in blob for k in kws):
                return str(rule.get("intent") or "educational")
        if ctype == "success_story":
            return "success_story"
        return "educational"

    def select(
        self,
        *,
        intent: str,
        legacy_visual_mode: str = "",
        message: dict[str, Any] | None = None,
        variant_index: int = 0,
    ) -> dict[str, Any]:
        """Return pattern dict with id + library fields."""
        legacy_map = self._intents.get("legacy_mode_patterns") or {}
        preferred: list[str] = []
        if legacy_visual_mode and legacy_visual_mode in legacy_map:
            preferred.append(str(legacy_map[legacy_visual_mode]))

        intent_cfg = (self._intents.get("intents") or {}).get(intent) or {}
        preferred.extend(str(x) for x in (intent_cfg.get("preferred") or []))

        # Message-driven boosts
        msg = message or {}
        pain = str(msg.get("pain_point") or "").lower()
        if "news overload" in pain or "irrelevant" in pain:
            preferred.insert(0, "decision_funnel")
        if "due diligence" in pain:
            preferred.insert(0, "three_step_process")
        if float(msg.get("urgency") or 0) >= 0.65:
            preferred.insert(0, "warning_card")

        default = str(self._patterns.get("default_pattern") or "modern_infographic")
        catalog = self._patterns.get("patterns") or {}
        # Deduplicate preserving order
        seen: set[str] = set()
        ordered: list[str] = []
        for pid in preferred + [default]:
            if pid in catalog and pid not in seen:
                seen.add(pid)
                ordered.append(pid)
        if not ordered:
            ordered = [default] if default in catalog else list(catalog.keys())[:1]

        idx = variant_index % len(ordered)
        pattern_id = ordered[idx]
        spec = dict(catalog.get(pattern_id) or {})
        spec["id"] = pattern_id
        spec["intent"] = intent
        spec["alternates"] = ordered
        spec["always_avoid"] = list(self._patterns.get("always_avoid") or [])
        return spec
