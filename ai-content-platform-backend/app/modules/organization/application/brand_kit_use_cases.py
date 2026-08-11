"""Brand kit use cases: get, update."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.modules.organization.application.client_profile import (
    PROFILE_GENERATOR_PROMPT,
    PROFILE_SECTION_HEADINGS,
    PROFILE_TEMPLATE_OUTLINE,
    read_file_fallback_profile,
)
from app.modules.organization.domain.brand_kit_ports import BrandKitRepository

logger = get_logger(__name__)


def _serialize_kit(kit: Any) -> dict[str, Any]:
    profile = kit.client_profile_md
    if not (isinstance(profile, str) and profile.strip()):
        profile = read_file_fallback_profile()
        if profile == "No client profile configured.":
            profile = ""
    return {
        "id": str(kit.id),
        "organization_id": str(kit.organization_id),
        "name": kit.name,
        "primary_color": kit.primary_color,
        "secondary_color": kit.secondary_color,
        "accent_color": kit.accent_color,
        "font_heading": kit.font_heading,
        "font_body": kit.font_body,
        "logo_object_key": kit.logo_object_key,
        "tone_json": kit.tone_json,
        "footer_text": kit.footer_text,
        "services_line": kit.services_line,
        "client_profile_path": kit.client_profile_path,
        "client_profile_md": profile,
        "description": kit.description,
        "extra_settings": kit.extra_settings or {},
        "default_image_count": int((kit.extra_settings or {}).get("default_image_count") or 1),
        "auto_generate_image_with_draft": bool(
            (kit.extra_settings or {}).get("auto_generate_image_with_draft")
        ),
        "publishing_window": _publishing_window(kit.extra_settings),
        "publishing_targets": _publishing_targets(kit.extra_settings),
    }


def _publishing_window(extra: dict | None) -> str:
    mode = str((extra or {}).get("publishing_window") or "fortnight").strip().lower()
    return mode if mode in ("weekly", "fortnight") else "fortnight"


def _publishing_targets(extra: dict | None) -> dict[str, int] | None:
    raw = (extra or {}).get("publishing_targets")
    if not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    for key in ("educational", "success_story", "personal_achievement"):
        if key in raw and raw[key] is not None:
            lo, hi = (0, 5) if key == "personal_achievement" else (0, 10)
            out[key] = max(lo, min(hi, int(raw[key])))
    return out or None


class GetBrandKitUseCase:
    """Retrieve the brand kit for an organization."""

    def __init__(self, brand_repo: BrandKitRepository) -> None:
        self._brand_repo = brand_repo

    async def execute(self, org_id: uuid.UUID) -> dict[str, Any]:
        kit = await self._brand_repo.get_by_org_id(org_id)
        if kit is None:
            raise NotFoundError("BrandKit", str(org_id))
        return _serialize_kit(kit)


class UpdateBrandKitUseCase:
    """Partially update a brand kit."""

    def __init__(self, brand_repo: BrandKitRepository) -> None:
        self._brand_repo = brand_repo

    async def execute(
        self, org_id: uuid.UUID, updates: dict[str, Any]
    ) -> dict[str, Any]:
        kit = await self._brand_repo.get_by_org_id(org_id)
        if kit is None:
            raise NotFoundError("BrandKit", str(org_id))

        fields = dict(updates)
        default_count = fields.pop("default_image_count", None)
        auto_with_draft = fields.pop("auto_generate_image_with_draft", None)
        publishing_window = fields.pop("publishing_window", None)
        publishing_targets = fields.pop("publishing_targets", None)
        if (
            default_count is not None
            or auto_with_draft is not None
            or publishing_window is not None
            or publishing_targets is not None
        ):
            extra = dict(fields.get("extra_settings") or kit.extra_settings or {})
            if default_count is not None:
                extra["default_image_count"] = max(1, min(4, int(default_count)))
            if auto_with_draft is not None:
                extra["auto_generate_image_with_draft"] = bool(auto_with_draft)
            if publishing_window is not None:
                mode = str(publishing_window).strip().lower()
                if mode not in ("weekly", "fortnight"):
                    mode = "fortnight"
                extra["publishing_window"] = mode
            if publishing_targets is not None:
                if isinstance(publishing_targets, dict):
                    cleaned: dict[str, int] = {}
                    for key in ("educational", "success_story", "personal_achievement"):
                        if key in publishing_targets and publishing_targets[key] is not None:
                            lo, hi = (0, 5) if key == "personal_achievement" else (0, 10)
                            cleaned[key] = max(lo, min(hi, int(publishing_targets[key])))
                    extra["publishing_targets"] = cleaned
                else:
                    extra.pop("publishing_targets", None)
            fields["extra_settings"] = extra

        if "client_profile_md" in fields and fields["client_profile_md"] is not None:
            fields["client_profile_md"] = str(fields["client_profile_md"]).strip() or None

        updated_kit = await self._brand_repo.update(kit.id, fields)
        logger.info("BrandKit updated: org_id=%s fields=%s", org_id, list(fields.keys()))
        if updated_kit is None:
            raise NotFoundError("BrandKit", str(org_id))
        return _serialize_kit(updated_kit)


def get_profile_template() -> dict[str, Any]:
    return {
        "generator_prompt": PROFILE_GENERATOR_PROMPT,
        "outline": PROFILE_TEMPLATE_OUTLINE,
        "section_headings": list(PROFILE_SECTION_HEADINGS),
    }
