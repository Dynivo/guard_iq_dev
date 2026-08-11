"""Visual policy engine — brand/compliance gates before generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import (
    CompositionPlan,
    EnrichedVisualBrief,
    ScenePlan,
    VisualPolicyResult,
)

# Ban only paragraph / body-copy requests. Short 2–4 word infographic labels are allowed.
_REQUEST_PARAGRAPH_TEXT = re.compile(
    r"\bparagraphs?\s+of\s+(?:body\s+)?(?:text|copy)\b"
    r"|\bbody\s+copy\s+in\s+(?:the\s+)?image\b"
    r"|\breadable\s+paragraphs?\b"
    r"|\btiny\s+illegible\s+text\s+walls\b"
    r"|\bfull\s+sentences?\s+in\s+(?:the\s+)?image\b"
    r"|\bwalls?\s+of\s+text\b",
    re.I,
)
_NEGATED_PARAGRAPH = re.compile(
    r"\b(?:no|not|without|avoid|ban|forbid|zero|never)\b.{0,48}\b"
    r"(?:paragraphs?|body\s+copy|walls?\s+of\s+text|illegible\s+text)\b",
    re.I,
)
_LOGO_REQUEST = re.compile(r"\blogo\b", re.I)
_LOGO_BAN = re.compile(
    r"\b(?:no|not|without|avoid|ban)\b.{0,20}\b(?:linkedin\s+)?logo\b",
    re.I,
)


class DefaultVisualPolicyEngine:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_yaml("policy.yaml", config_dir)

    def validate(
        self,
        brief: EnrichedVisualBrief,
        scene: ScenePlan,
        composition: CompositionPlan,
        *,
        brand: dict[str, Any] | None = None,
    ) -> VisualPolicyResult:
        reasons: list[str] = []
        brand = brand or {}
        meta = brief.metadata or {}
        # Positive prompt fields only — negative prompts often say "no paragraphs"
        # and must not trip restricted gates.
        positive_blob = " ".join(
            [
                brief.scene_hint,
                brief.theme,
                brief.purpose,
                " ".join(scene.objects),
                " ".join(scene.icons),
                str(meta.get("must_depict") or ""),
                str(meta.get("short_labels") or ""),
            ]
        )
        safety_blob = " ".join(
            [
                positive_blob,
                brief.negative_prompt,
            ]
        ).lower()

        unsafe_ok = True
        for kw in self._cfg.get("unsafe_keywords") or []:
            if str(kw).lower() in safety_blob:
                unsafe_ok = False
                reasons.append(f"unsafe:{kw}")

        forbidden_ok = True
        for sym in self._cfg.get("forbidden_symbols") or []:
            if str(sym).lower() in safety_blob:
                forbidden_ok = False
                reasons.append(f"forbidden:{sym}")

        # Short labels are allowed for educational infographics (client house style).
        # Only fail when the prompt asks for paragraphs / body copy walls.
        restricted_ok = True
        asks_paragraphs = bool(_REQUEST_PARAGRAPH_TEXT.search(positive_blob))
        negated = bool(_NEGATED_PARAGRAPH.search(positive_blob))
        if asks_paragraphs and not negated:
            restricted_ok = False
            reasons.append("restricted:paragraph_body_text")

        size_ok = (
            int(self._cfg.get("min_width") or 512)
            <= composition.width
            <= int(self._cfg.get("max_width") or 4096)
            and int(self._cfg.get("min_height") or 512)
            <= composition.height
            <= int(self._cfg.get("max_height") or 4096)
        )
        if not size_ok:
            reasons.append("image_size_out_of_range")

        safe_area_ok = True
        if self._cfg.get("require_typography_safe_area", True) and not brief.typography_safe_area:
            safe_area_ok = False
            reasons.append("missing_typography_safe_area")

        neg_ok = True
        if self._cfg.get("require_negative_ban_paragraphs", True) or self._cfg.get(
            "require_negative_no_text", False
        ):
            neg = brief.negative_prompt.lower()
            # Accept either legacy "text" ban or modern paragraph/illegible ban
            if not any(
                token in neg
                for token in ("paragraph", "illegible", "misspelled", "body copy", "text")
            ):
                neg_ok = False
                reasons.append("negative_prompt_missing_text_quality_ban")

        brand_ok = True
        primary = str(brand.get("primary_color") or "")
        if primary and not primary.startswith("#"):
            brand_ok = False
            reasons.append("invalid_brand_hex")

        logo_ok = True
        if self._cfg.get("logo_policy") == "no_generated_logo_in_diffusion":
            hint = brief.scene_hint or ""
            neg = brief.negative_prompt or ""
            if _LOGO_REQUEST.search(hint) and not (
                _LOGO_BAN.search(hint) or _LOGO_BAN.search(neg) or "no logo" in neg.lower()
            ):
                # Advisory only — does not fail the gate
                reasons.append("logo_hint_present")
                logo_ok = False

        compliance_ok = unsafe_ok and forbidden_ok
        passed = all(
            [
                unsafe_ok,
                forbidden_ok,
                restricted_ok,
                size_ok,
                safe_area_ok,
                neg_ok,
                brand_ok,
            ]
        )
        if self._cfg.get("fail_closed", True) is False:
            passed = True

        score = max(0.0, 1.0 - 0.12 * len(reasons))
        return VisualPolicyResult(
            passed=passed,
            brand_colors_ok=brand_ok,
            restricted_elements_ok=restricted_ok,
            forbidden_symbols_ok=forbidden_ok,
            unsafe_content_ok=unsafe_ok,
            compliance_ok=compliance_ok,
            logo_usage_ok=logo_ok,
            typography_safe_area_ok=safe_area_ok,
            image_size_ok=size_ok,
            reason_codes=tuple(reasons),
            score=round(score, 4),
            metadata={
                "brand_name": brand.get("name"),
                "allows_short_labels": True,
            },
        )
