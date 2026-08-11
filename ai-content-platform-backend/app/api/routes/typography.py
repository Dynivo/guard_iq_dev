"""Typography asset routes — Brand & Typography Engine (no PDF/carousel)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import MembershipRole
from app.core.exceptions import NotFoundError
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.infrastructure.postgres.models.branding import BrandKit
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.imaging import ImageJob
from app.infrastructure.postgres.models.typography import TypographyAssetRow
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.image.application.layout import DefaultLayoutPlanner
from app.modules.image.domain.models import CompositionPlan, EnrichedVisualBrief, ScenePlan
from app.modules.typography.application.factory import TypographyFactory
from app.modules.typography.domain.models import (
    LogoPlacementOptions,
    TypographyCopy,
    TypographyPipelineRequest,
)

router = APIRouter(tags=["typography"])
_engine = TypographyFactory.create_memory()


class LogoOptionsRequest(BaseModel):
    include_logo: bool = False
    # brand_default | learned → use Visual DNA preferred corner from brand posts
    position: str = Field(
        default="brand_default",
        pattern="^(top_left|top_right|bottom_left|bottom_right|center|custom|brand_default|learned)$",
    )
    custom_x: float | None = Field(default=None, ge=0.0, le=1.0)
    custom_y: float | None = Field(default=None, ge=0.0, le=1.0)
    size: str = Field(default="m", pattern="^(s|m|l|S|M|L)$")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    margin: float = Field(default=0.04, ge=0.0, le=0.25)
    safe_area: bool = True


class TypographyGenerateRequest(BaseModel):
    image_job_id: uuid.UUID | None = None
    target_width: int = Field(default=1080, ge=512, le=4096)
    target_height: int = Field(default=1350, ge=512, le=4096)
    brand_variant: str = "dark"
    template_id: str = "default"
    illustration_ref: str = ""
    logo: LogoOptionsRequest | None = None


def _brand_dict(kit: BrandKit | None) -> dict[str, Any]:
    if kit is None:
        return {"name": "Brand", "primary_color": "#0A1F2B", "accent_color": "#1A5CB0", "font_heading": "Inter", "font_body": "Inter"}
    return {
        "id": str(kit.id),
        "name": kit.name,
        "primary_color": kit.primary_color,
        "secondary_color": kit.secondary_color,
        "accent_color": kit.accent_color,
        "font_heading": kit.font_heading,
        "font_body": kit.font_body,
        "logo_object_key": kit.logo_object_key,
        "footer_text": kit.footer_text,
        "services_line": kit.services_line,
    }


@router.post("/drafts/{draft_id}/typography/generate")
async def generate_typography(
    draft_id: uuid.UUID,
    body: TypographyGenerateRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    org_id = current_user.organization_id
    draft = await session.get(Draft, draft_id)
    if draft is None or draft.organization_id != org_id:
        raise NotFoundError("Draft", str(draft_id))

    job = None
    if body.image_job_id:
        job = await session.get(ImageJob, body.image_job_id)
        if job is None or job.organization_id != org_id:
            raise NotFoundError("ImageJob", str(body.image_job_id))

    layout_plan = (job.layout_plan_json if job else None) or {}
    if not layout_plan:
        brief = EnrichedVisualBrief.from_dict(draft.visual_brief_json or {})
        scene = ScenePlan(icons=brief.icons, reading_direction="ltr_top_to_bottom")
        composition = CompositionPlan(width=body.target_width, height=body.target_height)
        layout_plan = DefaultLayoutPlanner().plan(
            brief=brief,
            scene=scene,
            composition=composition,
            image_width=body.target_width,
            image_height=body.target_height,
        ).to_dict()

    brand_row = (
        await session.execute(select(BrandKit).where(BrandKit.organization_id == org_id).limit(1))
    ).scalar_one_or_none()

    from app.modules.brand_intelligence.application.logo_placement import (
        resolve_logo_placement_defaults,
    )
    from app.modules.brand_intelligence.application.use_cases import BrandIntelligenceUseCases

    visual_dna: dict[str, Any] = {}
    try:
        bi = BrandIntelligenceUseCases(session)
        default_profile = await bi.profiles.get_default(org_id)
        if default_profile:
            mem = await bi.memories.get_active(org_id, default_profile.id)
            if mem and mem.visual_dna_json:
                visual_dna = dict(mem.visual_dna_json)
    except Exception:  # noqa: BLE001
        visual_dna = {}

    logo_req = body.logo or LogoOptionsRequest()
    resolved = resolve_logo_placement_defaults(
        visual_dna,
        has_logo_asset=bool(brand_row and brand_row.logo_object_key),
        override=logo_req.model_dump(),
    )
    pos = str(resolved["position"])
    if pos in ("brand_default", "learned"):
        pos = str(resolved.get("learned_position") or "bottom_right")
    logo_opts = LogoPlacementOptions(
        include_logo=bool(resolved["include_logo"]),
        position=pos,
        custom_x=resolved.get("custom_x"),
        custom_y=resolved.get("custom_y"),
        size=str(resolved.get("size") or "m").lower(),
        opacity=float(resolved.get("opacity") or 1.0),
        margin=float(resolved.get("margin") or 0.04),
        safe_area=bool(resolved.get("safe_area", True)),
    )
    logo_data_uri: str | None = None
    if logo_opts.include_logo and brand_row and brand_row.logo_object_key:
        try:
            from app.infrastructure.storage import get_storage_provider

            raw = get_storage_provider().get_bytes(brand_row.logo_object_key)
            import base64

            key = brand_row.logo_object_key.lower()
            mime = "image/png"
            if key.endswith(".jpg") or key.endswith(".jpeg"):
                mime = "image/jpeg"
            elif key.endswith(".svg"):
                mime = "image/svg+xml"
            elif key.endswith(".webp"):
                mime = "image/webp"
            logo_data_uri = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        except Exception:  # noqa: BLE001
            logo_data_uri = None

    result = await _engine.run(
        TypographyPipelineRequest(
            organization_id=str(org_id),
            draft_id=str(draft_id),
            image_job_id=str(job.id) if job else "",
            layout_plan=layout_plan,
            brand_kit=_brand_dict(brand_row),
            copy=TypographyCopy(
                headline=draft.hook or "Headline",
                subtitle=(draft.generated_text or "")[:160],
                cta=draft.cta or "",
                footer=(brand_row.footer_text if brand_row else "") or "",
            ),
            illustration_ref=body.illustration_ref,
            target_width=body.target_width,
            target_height=body.target_height,
            brand_variant=body.brand_variant,
            template_id=body.template_id,
            correlation_id=getattr(request.state, "request_id", "") or "",
            logo_options=logo_opts,
            logo_data_uri=logo_data_uri,
        )
    )

    asset = result.asset
    row = TypographyAssetRow(
        organization_id=org_id,
        draft_id=draft_id,
        image_job_id=job.id if job else None,
        parent_asset_id=uuid.UUID(asset.parent_asset_id) if asset.parent_asset_id else None,
        status=result.status,
        svg_text=asset.svg,
        layers_json=[layer.to_dict() for layer in asset.layers],
        layout_enrichment_json=asset.layout.to_dict() if asset.layout else None,
        typography_plan_json=asset.typography_plan.to_dict() if asset.typography_plan else None,
        brand_application_json=asset.brand.to_dict() if asset.brand else None,
        overlay_validation_json=(
            asset.overlay_validation.to_dict() if asset.overlay_validation else None
        ),
        brand_validation_json=asset.brand_validation.to_dict() if asset.brand_validation else None,
        slide_composition_json=(
            asset.slide_composition.to_dict() if asset.slide_composition else None
        ),
        typography_intelligence_json=(
            asset.intelligence.to_dict() if asset.intelligence else None
        ),
        design_tokens_json=(
            asset.brand.design_tokens.to_dict()
            if asset.brand and asset.brand.design_tokens
            else None
        ),
        width=asset.width,
        height=asset.height,
        version=asset.version,
        accessibility_score=(
            asset.overlay_validation.accessibility_score if asset.overlay_validation else None
        ),
        brand_score=asset.brand_validation.brand_score if asset.brand_validation else None,
        typography_score=(
            asset.overlay_validation.typography_score if asset.overlay_validation else None
        ),
        contrast_score=asset.overlay_validation.contrast_score if asset.overlay_validation else None,
        metadata_json=dict(asset.metadata),
    )
    # Use engine asset id as PK when possible
    try:
        row.id = uuid.UUID(asset.asset_id)
    except ValueError:
        pass
    session.add(row)
    await session.flush()

    return success_response(
        {
            **result.to_dict(),
            "persisted_id": str(row.id),
        },
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/typography/assets/{asset_id}")
async def get_typography_asset(
    asset_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    row = await session.get(TypographyAssetRow, asset_id)
    if row is None or row.organization_id != current_user.organization_id:
        # Fallback to memory store
        mem = _engine.store.get(str(asset_id))
        if mem is None:
            raise NotFoundError("TypographyAsset", str(asset_id))
        return success_response(mem.to_dict(), request_id=getattr(request.state, "request_id", ""))
    return success_response(
        {
            "asset_id": str(row.id),
            "status": row.status,
            "svg": row.svg_text,
            "layers": row.layers_json,
            "width": row.width,
            "height": row.height,
            "version": row.version,
            "layout": row.layout_enrichment_json,
            "typography_plan": row.typography_plan_json,
            "brand": row.brand_application_json,
            "overlay_validation": row.overlay_validation_json,
            "brand_validation": row.brand_validation_json,
            "slide_composition": row.slide_composition_json,
            "intelligence": row.typography_intelligence_json,
            "design_tokens": row.design_tokens_json,
            "scores": {
                "accessibility": row.accessibility_score,
                "brand": row.brand_score,
                "typography": row.typography_score,
                "contrast": row.contrast_score,
            },
        },
        request_id=getattr(request.state, "request_id", ""),
    )
