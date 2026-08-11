"""Carousel planner — deterministic slide sequence from draft + typography hints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.carousel.application.config_loader import load_carousel
from app.modules.carousel.domain.models import CarouselPlan, PlannedSlide


class DefaultCarouselPlanner:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._cfg = load_carousel("planner.yaml", config_dir)

    def plan(
        self,
        draft_snapshot: dict[str, Any],
        *,
        typography_assets: tuple[dict[str, Any], ...] = (),
        image_refs: tuple[str, ...] = (),
    ) -> CarouselPlan:
        min_s = int(self._cfg.get("min_slides") or 3)
        max_s = int(self._cfg.get("max_slides") or 12)
        aliases = dict(self._cfg.get("purpose_aliases") or {})
        default_seq = list(self._cfg.get("default_sequence") or [])

        slides_raw = self._extract_slides(draft_snapshot)
        typo_meta = self._typography_hints(typography_assets)
        image_cycle = list(image_refs) or [""]

        planned: list[PlannedSlide] = []
        if slides_raw:
            for i, raw in enumerate(slides_raw[:max_s]):
                role = str(raw.get("role") or raw.get("purpose") or default_seq[i % len(default_seq)])
                purpose = str(aliases.get(role) or role or "educational")
                hint = typo_meta[i % len(typo_meta)] if typo_meta else {}
                planned.append(
                    PlannedSlide(
                        index=i,
                        purpose=purpose,
                        title=str(raw.get("title") or raw.get("headline") or "")[:200],
                        body=str(raw.get("body") or "")[:800],
                        transition_hint=str(hint.get("transition_hint") or "none"),
                        continuation_hint=str(hint.get("continuation_hint") or "none"),
                        preferred_layout=str(hint.get("preferred_layout") or "default"),
                        typography_asset_id=hint.get("asset_id"),
                        image_ref=image_cycle[i % len(image_cycle)],
                        metadata={"source": "draft_carousel", "role": role},
                    )
                )
        else:
            hook = str(draft_snapshot.get("hook") or "Key insight")
            cta = str(draft_snapshot.get("cta") or "Follow for more")
            body = str(
                draft_snapshot.get("edited_text")
                or draft_snapshot.get("generated_text")
                or draft_snapshot.get("body")
                or ""
            )
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()] or [body or hook]
            seq = default_seq[:]
            while len(seq) < min_s:
                seq.append("educational")
            seq = seq[: max(min_s, min(max_s, len(seq)))]
            for i, purpose in enumerate(seq):
                hint = typo_meta[i % len(typo_meta)] if typo_meta else {}
                title = hook if purpose == "hook" else (cta if purpose == "cta" else paragraphs[i % len(paragraphs)][:120])
                planned.append(
                    PlannedSlide(
                        index=i,
                        purpose=str(aliases.get(purpose) or purpose),
                        title=title[:200],
                        body=paragraphs[i % len(paragraphs)][:800],
                        transition_hint=str(hint.get("transition_hint") or "none"),
                        continuation_hint=str(hint.get("continuation_hint") or "none"),
                        preferred_layout=str(hint.get("preferred_layout") or "default"),
                        typography_asset_id=hint.get("asset_id"),
                        image_ref=image_cycle[i % len(image_cycle)],
                        metadata={"source": "draft_fallback"},
                    )
                )

        if len(planned) < min_s and planned:
            while len(planned) < min_s:
                base = planned[-1]
                planned.append(
                    PlannedSlide(
                        index=len(planned),
                        purpose="educational",
                        title=base.title,
                        body=base.body,
                        transition_hint=base.transition_hint,
                        preferred_layout=base.preferred_layout,
                        typography_asset_id=base.typography_asset_id,
                        image_ref=base.image_ref,
                        metadata={"source": "pad_min_slides"},
                    )
                )

        return CarouselPlan(
            slides=tuple(planned),
            slide_count=len(planned),
            sequence=tuple(s.purpose for s in planned),
            metadata={
                "mutates_draft": False,
                "uses_llm": False,
                "typography_asset_count": len(typography_assets),
            },
        )

    def _extract_slides(self, draft: dict[str, Any]) -> list[dict[str, Any]]:
        car = draft.get("carousel")
        if isinstance(car, dict) and car.get("slides"):
            return [x for x in car["slides"] if isinstance(x, dict)]
        outline = draft.get("slide_outline") or draft.get("slides") or []
        return [x for x in outline if isinstance(x, dict)]

    def _typography_hints(
        self, assets: tuple[dict[str, Any], ...]
    ) -> list[dict[str, Any]]:
        hints: list[dict[str, Any]] = []
        for asset in assets:
            sc = asset.get("slide_composition") or {}
            if not isinstance(sc, dict):
                sc = {}
            hints.append(
                {
                    "asset_id": asset.get("asset_id"),
                    "transition_hint": sc.get("transition_hint") or "none",
                    "continuation_hint": sc.get("continuation_hint") or "none",
                    "preferred_layout": sc.get("preferred_layout") or "default",
                }
            )
        return hints
