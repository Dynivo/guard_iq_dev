"""Export profile registry — LinkedIn / Instagram / Presentation / Print / Mobile."""

from __future__ import annotations

from pathlib import Path

from app.modules.carousel.application.config_loader import load_yaml
from app.modules.carousel.domain.models import ExportProfile, LayoutConstraints

_PROFILE_IDS = ("linkedin", "instagram", "presentation", "print", "mobile")


class ExportProfileRegistry:
    def __init__(self, config_dir: Path | None = None) -> None:
        if config_dir is not None:
            self._root = Path(config_dir) / "profiles"
        else:
            self._root = Path(__file__).resolve().parents[4] / "configs" / "carousel" / "profiles"
        self._cache: dict[str, ExportProfile] = {}
        for pid in _PROFILE_IDS:
            self._cache[pid] = self._load(pid)

    def list_ids(self) -> tuple[str, ...]:
        return _PROFILE_IDS

    def get(self, profile_id: str) -> ExportProfile:
        key = profile_id if profile_id in self._cache else "linkedin"
        return self._cache[key]

    def layout_constraints(self, profile_id: str) -> LayoutConstraints:
        profile = self.get(profile_id)
        raw = self._raw(profile.profile_id)
        safe = profile.safe_area
        safe_areas: tuple[dict, ...] = (dict(safe),) if safe else ()
        return LayoutConstraints(
            margins=dict(profile.margins)
            or {"top": 0.04, "right": 0.06, "bottom": 0.04, "left": 0.06},
            padding=dict(raw.get("padding") or {"top": 0.02, "right": 0.02, "bottom": 0.02, "left": 0.02}),
            safe_areas=safe_areas,
            bleed=float(profile.bleed),
            grid_columns=int(raw.get("grid_columns") or 12),
            grid_gutter=float(raw.get("grid_gutter") or 0.02),
            alignment_rules=dict(raw.get("alignment_rules") or {}),
            metadata={"profile_id": profile.profile_id},
        )

    def _raw(self, profile_id: str) -> dict:
        return load_yaml(self._root / f"{profile_id}.yaml")

    def _load(self, profile_id: str) -> ExportProfile:
        raw = self._raw(profile_id)
        return ExportProfile(
            profile_id=str(raw.get("id") or profile_id),
            name=str(raw.get("name") or profile_id.title()),
            width=int(raw.get("width") or 1080),
            height=int(raw.get("height") or 1350),
            margins=dict(raw.get("margins") or {}),
            safe_area=dict(raw.get("safe_area") or {}),
            render_strategy=str(raw.get("render_strategy") or "svg_html_playwright"),
            formats=tuple(str(x) for x in (raw.get("formats") or ("png", "pdf", "zip"))),
            bleed=float(raw.get("bleed") or 0.0),
            metadata={"source": f"{profile_id}.yaml"},
        )
