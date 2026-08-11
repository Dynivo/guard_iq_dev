"""Visual Brief Generator — structured brief only; never generates images."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.content.domain.models import StructuredDraft, VisualBrief

_DEFAULT = Path(__file__).resolve().parents[5] / "configs" / "content" / "generation"


def _blob(*parts: str) -> str:
    return " ".join(p for p in parts if p).lower()


class DefaultVisualBriefGenerator:
    def __init__(self, config_dir: Path | None = None) -> None:
        path = (config_dir or _DEFAULT) / "visual_brief.yaml"
        self._cfg: dict[str, Any] = {}
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                self._cfg = raw

    def _pick_scene(self, text: str, ctype: str, direction: str) -> str:
        templates = self._cfg.get("scene_templates") or {}
        if direction.strip():
            return direction.strip()
        t = text.lower()
        if any(k in t for k in ("bec", "invoice", "phishing", "lookalike", "fake email")):
            return str(templates.get("security_bec") or templates.get("default_branded") or "")
        if any(k in t for k in ("cia triad", "confidentiality", "integrity", "availability")):
            return str(templates.get("cia_framework") or templates.get("default_branded") or "")
        if any(
            k in t
            for k in (
                "acqui",
                "invest",
                "million",
                "senior living",
                "care home",
                "healthcare",
                "hospital",
            )
        ):
            return str(
                templates.get("acquisition_investment")
                or templates.get("care_healthcare")
                or templates.get("default_branded")
                or ""
            )
        if any(k in t for k in ("care", "cqc", "dspt", "patient", "clinical")):
            return str(templates.get("care_healthcare") or templates.get("default_branded") or "")
        if ctype in ("security_alert", "compliance_update"):
            return str(templates.get("security_bec") or templates.get("default_branded") or "")
        return str(
            templates.get("default_branded")
            or f"Premium flat branded LinkedIn illustration for {ctype.replace('_', ' ')}"
        )

    def _pick_style(self, text: str, plan_style: str, default_style: str) -> str:
        if plan_style:
            return plan_style
        mapping = self._cfg.get("style_by_keywords") or {}
        t = text.lower()
        for key, style in mapping.items():
            if key == "default":
                continue
            if key in t:
                return str(style)
        return str(mapping.get("default") or default_style or "branded_flat_illustration")

    def generate(
        self,
        draft: StructuredDraft,
        *,
        content_plan: dict[str, Any] | None = None,
    ) -> VisualBrief:
        plan = content_plan or {}
        defaults = self._cfg.get("defaults") or {}
        tone = str(plan.get("tone") or draft.metadata.get("tone") or "professional")
        ctype = draft.content_type or str(plan.get("content_type") or "educational")
        fmt = draft.format or str(plan.get("format") or "single")

        emotion_map = self._cfg.get("emotion_by_tone") or {}
        intent_map = self._cfg.get("intent_by_type") or {}
        icons_map = self._cfg.get("icons_by_type") or {}
        info_map = self._cfg.get("infographic_by_format") or {}

        text = _blob(draft.hook, draft.body, draft.cta, str(plan.get("topic") or ""))
        direction = str(plan.get("visual_direction") or "")
        style = self._pick_style(
            text,
            str(plan.get("image_style") or ""),
            str(defaults.get("illustration_style") or "branded_flat_illustration"),
        )
        scene = self._pick_scene(text, ctype, direction)
        focal = draft.hook[:120] if draft.hook else "primary message"
        icons = tuple(
            icons_map.get(ctype) or icons_map.get("default") or defaults.get("icons") or ()
        )
        if isinstance(icons, list):
            icons = tuple(str(i) for i in icons)
        infos = tuple(info_map.get(fmt) or info_map.get("single") or ())
        if isinstance(infos, list):
            infos = tuple(str(i) for i in infos)
        palette = defaults.get("color_palette") or ()
        if isinstance(palette, list):
            palette = tuple(str(c) for c in palette)

        # Educational / framework graphics keep negative softer so typography path can add headlines
        negative = str(defaults.get("negative_prompt") or "")
        if style in ("educational_infographic", "dark_cyber_brand_graphic"):
            negative = (
                "photorealistic stock photo, handshake, watermark, logo spam, low quality, "
                "blurry, cluttered collage, meme style, tiny illegible text walls"
            )

        brief = VisualBrief(
            illustration_style=style,
            scene=scene,
            composition=str(defaults.get("composition") or "centered_hero_with_safe_margin"),
            focal_point=focal,
            camera_angle=str(defaults.get("camera_angle") or "eye_level"),
            icon_suggestions=icons,
            infographic_suggestions=infos,
            negative_prompt=negative,
            typography_safe_area=str(
                defaults.get("typography_safe_area") or "top_third_or_bottom_band"
            ),
            color_palette=palette,
            visual_hierarchy="headline > supporting visual > CTA cue",
            emotion=str(emotion_map.get(tone) or "calm_confidence"),
            visual_intent=str(
                intent_map.get(ctype) or intent_map.get("default") or "scroll_stop_and_educate"
            ),
            metadata={
                "source": "deterministic_visual_brief",
                "never_generates_images": True,
                "style_selected": style,
            },
        )
        return brief
