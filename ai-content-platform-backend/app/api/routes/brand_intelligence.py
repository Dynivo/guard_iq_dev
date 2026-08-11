"""Brand Intelligence HTTP API."""

from __future__ import annotations

import base64
import mimetypes
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.schemas.brand_intelligence import (
    CreateImportRequest,
    CreateProfileRequest,
    LinkedInUrlImportRequest,
    LogoVariantRequest,
    NeverSayUpdateRequest,
    ReviewEditRequest,
)
from app.api.schemas.envelope import success_response
from app.core.constants.enums import MembershipRole
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.infrastructure.storage import get_storage_provider
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.brand_intelligence.application.use_cases import BrandIntelligenceUseCases
from app.modules.brand_intelligence.domain.models import LogoAssetSet
from app.shared.result import Failure

router = APIRouter(prefix="/brand-intelligence", tags=["brand-intelligence"])


def _unwrap(result: Any) -> Any:
    if isinstance(result, Failure) or getattr(result, "is_failure", False):
        code = getattr(result, "code", "error")
        message = getattr(result, "message", "request failed")
        status_code = status.HTTP_404_NOT_FOUND if "not_found" in code else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})
    return result.value


@router.get("/profiles")
async def list_profiles(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = await uc.list_profiles(current_user.organization_id)
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/profiles", status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: CreateProfileRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = await uc.create_profile(
        current_user.organization_id,
        kind=body.kind,
        name=body.name,
        is_default=body.is_default,
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/linkedin/import", status_code=status.HTTP_202_ACCEPTED)
async def import_from_linkedin_url(
    body: LinkedInUrlImportRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Paste LinkedIn URL only — fetch profile/posts/images via session, then analyze."""
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(
        await uc.import_from_linkedin_url(
            current_user.organization_id,
            linkedin_url=body.linkedin_url,
            brand_profile_id=body.brand_profile_id,
            profile_name=body.profile_name,
            max_posts=body.max_posts,
            website_url=body.website_url,
            correlation_id=getattr(request.state, "request_id", ""),
        )
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/imports", status_code=status.HTTP_201_CREATED)
async def create_import(
    body: CreateImportRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    source_mix = {
        "linkedin_url": body.linkedin_url,
        "linkedin_about": body.linkedin_about,
        "linkedin_headline": body.linkedin_headline,
        "linkedin_display_name": body.linkedin_display_name,
        "linkedin_posts": body.linkedin_posts,
        "website_url": body.website_url,
        "max_pages": body.max_pages,
        "max_posts": body.max_posts,
        "use_playwright": body.use_playwright,
        "artifacts": body.artifacts,
        "sources": [
            s
            for s, present in (
                ("linkedin", bool(body.linkedin_url)),
                ("website", bool(body.website_url)),
                ("upload", bool(body.artifacts)),
            )
            if present
        ],
    }
    data = _unwrap(
        await uc.create_import(
            current_user.organization_id,
            profile_id=body.brand_profile_id,
            source_mix=source_mix,
        )
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/imports/{import_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_import(
    import_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(
        await uc.start_analyze(
            current_user.organization_id,
            import_id,
            correlation_id=getattr(request.state, "request_id", ""),
        )
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(await uc.get_job_progress(current_user.organization_id, job_id))
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/profiles/{profile_id}/memory")
async def get_memory(
    profile_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(await uc.get_memory(current_user.organization_id, profile_id))
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/profiles/{profile_id}/dashboard")
async def dashboard(
    profile_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(await uc.dashboard(current_user.organization_id, profile_id))
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/profiles/{profile_id}/hub")
async def profile_hub(
    profile_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Scraped LinkedIn/website sources + Brand Memory summary for Brand page."""
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(await uc.profile_hub(current_user.organization_id, profile_id))
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/profiles/{profile_id}/assets/upload")
async def upload_brand_asset(
    profile_id: uuid.UUID,
    request: Request,
    kind: str = Form(default="logo"),
    make_primary: bool = Form(default=True),
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Upload logo / guideline / image via StorageProvider; logos project to Brand Kit."""
    uc = BrandIntelligenceUseCases(session)
    profile = await uc.profiles.get(current_user.organization_id, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail={"code": "profile_not_found", "message": "Profile not found"})
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail={"code": "empty_file", "message": "Empty upload"})
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail={"code": "too_large", "message": "Max 20MB"})
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    ext = (file.filename or "bin").rsplit(".", 1)[-1].lower()[:12] if file.filename and "." in file.filename else "bin"
    asset_id = uuid.uuid4()
    key = f"{current_user.organization_id}/brand/{profile_id}/{kind}/{asset_id}.{ext}"
    stored = get_storage_provider().put_bytes(key, raw, content_type=mime)
    result: dict[str, Any] = {
        "kind": kind,
        "storage_key": stored.storage_key,
        "content_type": mime,
        "size_bytes": stored.size_bytes,
        "filename": file.filename,
    }
    if kind == "logo":
        existing = await uc.logos.get(current_user.organization_id, profile_id)
        logo = existing or LogoAssetSet(
            id=uuid.uuid4(),
            organization_id=current_user.organization_id,
            brand_profile_id=profile_id,
            variants_json={},
        )
        variants = dict(logo.variants_json)
        variants["primary" if make_primary else ext] = stored.storage_key
        logo.variants_json = variants
        if make_primary:
            logo.primary_key = stored.storage_key
        await uc.logos.upsert(logo)
        kit = await uc.brand_kits.get_by_org_id(current_user.organization_id)
        if kit and logo.primary_key:
            await uc.brand_kits.update(kit.id, {"logo_object_key": logo.primary_key})
        result["logo"] = {"primary_key": logo.primary_key, "variants": logo.variants_json}
    await session.commit()
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.get("/memories/{memory_id}/review")
async def get_review(
    memory_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(await uc.get_review(current_user.organization_id, memory_id))
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.patch("/reviews/{review_id}")
async def patch_review(
    review_id: uuid.UUID,
    body: ReviewEditRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(await uc.patch_review(current_user.organization_id, review_id, body.edits))
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/reviews/{review_id}/approve")
async def approve_review(
    review_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(
        await uc.approve_review(
            current_user.organization_id,
            review_id,
            user_id=current_user.user_id,
            correlation_id=getattr(request.state, "request_id", ""),
        )
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/reviews/{review_id}/reject")
async def reject_review(
    review_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(await uc.reject_review(current_user.organization_id, review_id))
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/memories/{memory_id}/versions/diff")
async def version_diff(
    memory_id: uuid.UUID,
    request: Request,
    v1: int,
    v2: int,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(await uc.version_diff(current_user.organization_id, memory_id, v1, v2))
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.get("/profiles/{profile_id}/never-say")
async def get_never_say(
    profile_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    policy = await uc.never_say.get(current_user.organization_id, profile_id)
    data = {
        "brand_profile_id": str(profile_id),
        "forbidden": policy.forbidden if policy else [],
        "discouraged": policy.discouraged if policy else [],
        "legal_restrictions": policy.legal_restrictions if policy else [],
        "compliance_restrictions": policy.compliance_restrictions if policy else [],
        "avoid_vocabulary": policy.avoid_vocabulary if policy else [],
        "never_use": policy.never_use if policy else [],
        "preferred_alternatives": policy.preferred_alternatives if policy else {},
    }
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.put("/profiles/{profile_id}/never-say")
async def put_never_say(
    profile_id: uuid.UUID,
    body: NeverSayUpdateRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    data = _unwrap(
        await uc.upsert_never_say(
            current_user.organization_id,
            profile_id,
            body.model_dump(exclude_none=True),
        )
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/profiles/{profile_id}/logos")
async def upsert_logo(
    profile_id: uuid.UUID,
    body: LogoVariantRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    existing = await uc.logos.get(current_user.organization_id, profile_id)
    logo = existing or LogoAssetSet(
        id=uuid.uuid4(),
        organization_id=current_user.organization_id,
        brand_profile_id=profile_id,
        variants_json={},
    )
    variants = dict(logo.variants_json)
    variants[body.variant] = body.storage_key
    logo.variants_json = variants
    if body.make_primary:
        logo.primary_key = body.storage_key
    await uc.logos.upsert(logo)
    # also push primary to brand kit
    kit = await uc.brand_kits.get_by_org_id(current_user.organization_id)
    if kit and logo.primary_key:
        await uc.brand_kits.update(kit.id, {"logo_object_key": logo.primary_key})
    await session.commit()
    return success_response(
        {"variants": logo.variants_json, "primary_key": logo.primary_key},
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post("/session/linkedin/start")
async def linkedin_session_start(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Bootstrap note for Playwright LinkedIn login (session ciphertext stored after client completes)."""
    _ = session
    return success_response(
        {
            "provider": "linkedin",
            "status": "ready_for_login",
            "instructions": (
                "Run local Playwright profile login for this organization, then POST "
                "/session/linkedin/save with storage_state JSON (base64) once."
            ),
            "organization_id": str(current_user.organization_id),
        },
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post("/session/linkedin/save")
async def linkedin_session_save(
    request: Request,
    body: dict[str, Any],
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    from app.modules.brand_intelligence.domain.models import BrowserSessionRecord

    uc = BrandIntelligenceUseCases(session)
    raw = body.get("storage_state_b64") or body.get("storage_state")
    if not raw:
        raise HTTPException(status_code=400, detail="storage_state_b64 required")
    if isinstance(raw, str) and not raw.strip().startswith("{"):
        ciphertext = base64.b64decode(raw)
    else:
        ciphertext = (raw if isinstance(raw, str) else str(raw)).encode("utf-8")
    await uc.sessions.save(
        BrowserSessionRecord(
            id=uuid.uuid4(),
            organization_id=current_user.organization_id,
            provider="linkedin",
            ciphertext=ciphertext,
        )
    )
    await session.commit()
    return success_response({"saved": True}, request_id=getattr(request.state, "request_id", ""))


@router.post("/session/linkedin/revoke")
async def linkedin_session_revoke(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.OWNER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    uc = BrandIntelligenceUseCases(session)
    await uc.sessions.revoke(current_user.organization_id, "linkedin")
    await session.commit()
    return success_response({"revoked": True}, request_id=getattr(request.state, "request_id", ""))


@router.get("/profiles/{profile_id}/logo-placement")
async def get_logo_placement(
    profile_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Suggested typography logo options (optional include + learned corner from brand posts)."""
    from app.modules.brand_intelligence.application.logo_placement import (
        resolve_logo_placement_defaults,
    )

    uc = BrandIntelligenceUseCases(session)
    profile = await uc.profiles.get(current_user.organization_id, profile_id)
    if not profile:
        raise HTTPException(
            status_code=404, detail={"code": "profile_not_found", "message": "Profile not found"}
        )
    mem = await uc.memories.get_active(current_user.organization_id, profile_id)
    logo = await uc.logos.get(current_user.organization_id, profile_id)
    kit = await uc.brand_kits.get_by_org_id(current_user.organization_id)
    data = resolve_logo_placement_defaults(
        mem.visual_dna_json if mem else None,
        has_logo_asset=bool(
            (logo and (logo.primary_key or logo.variants_json))
            or (kit and kit.logo_object_key)
        ),
    )
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/profiles/{profile_id}/sync-news-policy")
async def sync_news_policy(
    profile_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Project Brand Memory → relevance client profile + news source search queries."""
    from app.modules.brand_intelligence.application.news_policy_service import (
        BrandNewsPolicyService,
    )

    data = await BrandNewsPolicyService(session).sync_news_sources(
        current_user.organization_id, profile_id=profile_id
    )
    await session.commit()
    return success_response(data, request_id=getattr(request.state, "request_id", ""))


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_latest(
    body: CreateImportRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Incremental sync reuses create_import + analyze with watermark-aware source mix."""
    uc = BrandIntelligenceUseCases(session)
    source_mix = {
        "linkedin_url": body.linkedin_url,
        "linkedin_posts": body.linkedin_posts,
        "website_url": body.website_url,
        "artifacts": body.artifacts,
        "sync": True,
        "sources": ["linkedin"] if body.linkedin_url else [],
    }
    created = _unwrap(
        await uc.create_import(
            current_user.organization_id,
            profile_id=body.brand_profile_id,
            source_mix=source_mix,
        )
    )
    analyzed = _unwrap(
        await uc.start_analyze(
            current_user.organization_id,
            uuid.UUID(created["id"]),
            correlation_id=getattr(request.state, "request_id", ""),
        )
    )
    return success_response(
        {**created, **analyzed},
        request_id=getattr(request.state, "request_id", ""),
    )
