"""Visual brief enricher — structured only; never generates images."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.models import EnrichedVisualBrief


class DefaultVisualBriefEnricher:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_yaml("brief.yaml", config_dir)

    def enrich(
        self,
        draft: dict[str, Any],
        *,
        content_plan: dict[str, Any] | None = None,
        existing_brief: dict[str, Any] | None = None,
    ) -> EnrichedVisualBrief:
        plan = content_plan or {}
        meta = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
        raw = (
            existing_brief
            or draft.get("visual_brief")
            or meta.get("visual_brief")
            or meta.get("image_brief")
            or {}
        )
        if not isinstance(raw, dict):
            raw = {}
        base = EnrichedVisualBrief.from_dict(raw)
        defaults = self._cfg.get("defaults") or {}
        tone_map = defaults.get("visual_tone_by_emotion") or {}
        intent_map = self._cfg.get("purpose_by_intent") or {}

        emotion = base.emotion or base.visual_tone or "calm_confidence"
        intent = base.image_intent or "inform_and_engage"
        audience = (
            base.audience
            or str(plan.get("audience") or draft.get("audience") or defaults.get("audience") or "")
        )
        return EnrichedVisualBrief(
            illustration_style=base.illustration_style
            or str(plan.get("image_style") or "branded_illustration"),
            theme=base.theme or str(defaults.get("theme") or "professional_consulting"),
            purpose=base.purpose
            or str(intent_map.get(intent) or intent_map.get("default") or defaults.get("purpose") or ""),
            audience=audience,
            visual_tone=base.visual_tone
            or str(tone_map.get(emotion) or emotion or "confident_calm"),
            icons=base.icons,
            infographic_suggestions=base.infographic_suggestions,
            typography_safe_area=base.typography_safe_area or "bottom_third",
            negative_prompt=base.negative_prompt
            or (
                "any readable text, letters, words, captions, labels, misspelled text, "
                "photorealistic stock photo, handshake, watermark, logo spam, blurry, "
                "low quality, muddy brown background, dull washed-out colours"
            ),
            color_palette=base.color_palette
            or ("#0A1F2B", "#1A5CB0", "#0D7377", "#F4F7F5"),
            brand_direction=base.brand_direction
            or str(plan.get("visual_direction") or defaults.get("brand_direction") or ""),
            image_intent=intent,
            scene_hint=base.scene_hint
            or str(raw.get("scene") or plan.get("visual_direction") or "")
            or "Premium flat branded LinkedIn illustration using client Brand Kit colours",
            composition_hint=base.composition_hint or "centered_with_margin",
            focal_point=(
                base.focal_point
                if base.focal_point and len(base.focal_point) <= 48
                else "professional subject with clear prop"
            ),
            camera_angle=base.camera_angle or "eye_level",
            visual_hierarchy=base.visual_hierarchy
            or "headline space > focal subject > supporting icons",
            emotion=emotion,
            metadata={
                **base.metadata,
                "source": "visual_brief_enricher",
                "never_generates_images": True,
            },
        )
