"""Capture intake + To Post calendar + speech draft routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.core.constants import ContentType, DraftStatus, MembershipRole, PhotoMode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.speech.factory import get_speech_synthesis_provider
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.capture.application.use_cases import (
    CaptureVoiceUseCase,
    CreateCaptureSessionUseCase,
    GenerateFromCaptureUseCase,
    GetCaptureSessionUseCase,
    SaveCaptureTextUseCase,
    SaveFollowUpsUseCase,
    SuggestFollowUpsUseCase,
    UpdatePhotoModeUseCase,
    UploadCapturePhotosUseCase,
)

router = APIRouter(tags=["capture"])


class CaptureIntakeBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    content_type: str = Field(default=ContentType.SUCCESS_STORY)
    photo_mode: str = Field(default=PhotoMode.NONE)
    title: str | None = Field(default=None, max_length=500)


class ScheduleDraftBody(BaseModel):
    scheduled_for: str = Field(
        ...,
        description="ISO date or datetime for Mon–Fri posting slot",
    )


class CreateSessionBody(BaseModel):
    content_type: str = Field(default=ContentType.SUCCESS_STORY)
    photo_mode: str = Field(default=PhotoMode.NONE)
    title: str | None = Field(default=None, max_length=500)


class SaveTextBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    title: str | None = Field(default=None, max_length=500)
    photo_mode: str | None = None


class SaveFollowUpsBody(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class PhotoModeBody(BaseModel):
    photo_mode: str


# ── Legacy one-shot capture (kept for compatibility) ─────────


@router.post("/capture", status_code=201)
async def capture_intake(
    body: CaptureIntakeBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Mobile-friendly text capture for success/personal posts (photo mode metadata)."""
    allowed_types = {
        ContentType.EDUCATIONAL,
        ContentType.SUCCESS_STORY,
        ContentType.PERSONAL_ACHIEVEMENT,
        "educational",
        "success_story",
        "personal_achievement",
    }
    if body.content_type not in allowed_types:
        raise ValidationError(f"Unsupported content_type: {body.content_type}")
    if body.photo_mode not in {m.value for m in PhotoMode}:
        raise ValidationError(f"Unsupported photo_mode: {body.photo_mode}")

    hook = (body.title or body.text.strip().split("\n")[0])[:500]
    draft = Draft(
        organization_id=current_user.organization_id,
        article_id=None,
        content_type=body.content_type,
        status=DraftStatus.PENDING_REVIEW,
        generated_text=body.text.strip(),
        edited_text=body.text.strip(),
        hook=hook,
        metadata_json={
            "capture": True,
            "photo_mode": body.photo_mode,
            "source": "capture_intake",
        },
        version=1,
    )
    session.add(draft)
    await session.flush()
    return success_response(
        {
            "id": str(draft.id),
            "content_type": draft.content_type,
            "status": draft.status,
            "hook": draft.hook,
            "photo_mode": body.photo_mode,
        },
        request_id=getattr(request.state, "request_id", ""),
    )


# ── Capture sessions wizard ──────────────────────────────────


@router.post("/capture/sessions", status_code=201)
async def create_capture_session(
    body: CreateSessionBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await CreateCaptureSessionUseCase(session).execute(
        current_user.organization_id,
        content_type=body.content_type,
        photo_mode=body.photo_mode,
        title=body.title,
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.get("/capture/sessions/{session_id}")
async def get_capture_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await GetCaptureSessionUseCase(session).execute(
        current_user.organization_id, session_id
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/capture/sessions/{session_id}/text")
async def save_capture_text(
    session_id: uuid.UUID,
    body: SaveTextBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await SaveCaptureTextUseCase(session).execute(
        current_user.organization_id,
        session_id,
        text=body.text,
        title=body.title,
        photo_mode=body.photo_mode,
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/capture/sessions/{session_id}/voice")
async def capture_voice(
    session_id: uuid.UUID,
    request: Request,
    audio: UploadFile = File(...),
    append: bool = Form(default=False),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    data = await audio.read()
    content_type = audio.content_type or "audio/webm"
    result = await CaptureVoiceUseCase(session).execute(
        current_user.organization_id,
        session_id,
        audio_bytes=data,
        content_type=content_type,
        append=append,
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.get("/capture/sessions/{session_id}/follow-ups")
async def get_follow_ups(
    session_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await SuggestFollowUpsUseCase(session).execute(
        current_user.organization_id, session_id
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.patch("/capture/sessions/{session_id}/follow-ups")
async def save_follow_ups(
    session_id: uuid.UUID,
    body: SaveFollowUpsBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await SaveFollowUpsUseCase(session).execute(
        current_user.organization_id,
        session_id,
        answers=body.answers,
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.patch("/capture/sessions/{session_id}/photo-mode")
async def update_photo_mode(
    session_id: uuid.UUID,
    body: PhotoModeBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await UpdatePhotoModeUseCase(session).execute(
        current_user.organization_id,
        session_id,
        photo_mode=body.photo_mode,
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/capture/sessions/{session_id}/photos")
async def upload_capture_photos(
    session_id: uuid.UUID,
    request: Request,
    files: list[UploadFile] = File(...),
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    payloads: list[tuple[bytes, str, str]] = []
    for f in files:
        data = await f.read()
        payloads.append((data, f.filename or "photo.jpg", f.content_type or "image/jpeg"))
    result = await UploadCapturePhotosUseCase(session).execute(
        current_user.organization_id,
        session_id,
        files=payloads,
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/capture/sessions/{session_id}/generate", status_code=201)
async def generate_from_capture(
    session_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await GenerateFromCaptureUseCase(session).execute(
        current_user.organization_id, session_id
    )
    return success_response(result, request_id=getattr(request.state, "request_id", ""))


@router.post("/drafts/{draft_id}/speak")
async def speak_draft(
    draft_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """Optional TTS of the draft post text (Azure Speech or mock)."""
    draft = (
        await session.execute(
            select(Draft).where(
                Draft.id == draft_id,
                Draft.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()
    if draft is None:
        raise NotFoundError("Draft", str(draft_id))
    text = (draft.edited_text or draft.generated_text or "").strip()
    if draft.hook and draft.hook not in text:
        text = f"{draft.hook}\n\n{text}"
    if draft.cta and draft.cta not in text:
        text = f"{text}\n\n{draft.cta}"
    if not text:
        raise ValidationError("Draft has no text to speak")
    synth = get_speech_synthesis_provider()
    result = await synth.synthesize(text)
    return Response(
        content=result.audio_bytes,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'inline; filename="draft-{draft_id}.mp3"',
            "X-Speech-Provider": result.provider,
        },
    )


@router.get("/to-post")
async def list_to_post_queue(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Approved drafts with optional scheduled_for for the week calendar."""
    rows = (
        await session.execute(
            select(Draft)
            .where(
                Draft.organization_id == current_user.organization_id,
                Draft.status.in_(
                    (DraftStatus.APPROVED, DraftStatus.PUBLISHED, "approved", "published")
                ),
            )
            .order_by(Draft.updated_at.desc())
            .limit(100)
        )
    ).scalars().all()

    items = []
    for d in rows:
        meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
        items.append(
            {
                "id": str(d.id),
                "hook": d.hook,
                "content_type": d.content_type,
                "status": d.status,
                "scheduled_for": meta.get("scheduled_for"),
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
        )
    return success_response(
        {"items": items, "total": len(items), "quota_hint": "10 posts / fortnight"},
        request_id=getattr(request.state, "request_id", ""),
    )


@router.patch("/drafts/{draft_id}/schedule")
async def schedule_draft(
    draft_id: uuid.UUID,
    body: ScheduleDraftBody,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Assign a Mon–Fri posting slot via scheduled_for on draft metadata."""
    draft = (
        await session.execute(
            select(Draft).where(
                Draft.id == draft_id,
                Draft.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()
    if draft is None:
        raise NotFoundError("Draft", str(draft_id))

    raw = body.scheduled_for.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValidationError("scheduled_for must be an ISO date/datetime") from exc

    meta = dict(draft.metadata_json or {})
    meta["scheduled_for"] = parsed.date().isoformat()
    draft.metadata_json = meta
    await session.flush()
    return success_response(
        {
            "id": str(draft.id),
            "scheduled_for": meta["scheduled_for"],
            "status": draft.status,
        },
        request_id=getattr(request.state, "request_id", ""),
    )
