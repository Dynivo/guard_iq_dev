"""Capture session use cases: intake, voice, follow-ups, photos, generate draft."""

from __future__ import annotations

import json
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ContentType, DraftStatus, PhotoMode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.infrastructure.postgres.models.capture import CaptureAsset, CaptureSession
from app.infrastructure.postgres.models.carousel import MediaAsset
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.speech.factory import get_transcription_provider, get_translation_provider
from app.infrastructure.storage.factory import get_delivery_strategy, get_storage_provider
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.content.application.claims_guard import ClaimsGuard
from app.modules.content.application.generator import ContentGenerator
from app.modules.content.application.publishing_plan import PLAN_ORIGIN

logger = get_logger(__name__)

_ALLOWED_TYPES = {
    ContentType.SUCCESS_STORY,
    ContentType.PERSONAL_ACHIEVEMENT,
    ContentType.EDUCATIONAL,
    "success_story",
    "personal_achievement",
    "educational",
}

_THIN_STORY_FALLBACK: list[dict[str, str]] = [
    {
        "id": "clarify",
        "prompt": "Can you add one concrete detail — what happened, who benefited, and what changed?",
    },
]


def _story_looks_sufficient(story: str) -> bool:
    """Cheap heuristic: long enough + some concrete signal → likely no follow-ups."""
    words = [w for w in re.split(r"\s+", story.strip()) if w]
    if len(words) < 40:
        return False
    lower = story.lower()
    signals = (
        "because",
        "result",
        "outcome",
        "learned",
        "client",
        "we ",
        "i ",
        "%",
        "reduced",
        "improved",
        "fixed",
        "helped",
        "before",
        "after",
    )
    hits = sum(1 for s in signals if s in lower)
    return hits >= 2 and len(words) >= 60


def _parse_follow_up_payload(text: str) -> tuple[bool, list[dict[str, str]], str]:
    """Return (needed, questions, reason) from LLM JSON."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return False, [], ""
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False, [], ""
    if not isinstance(parsed, dict):
        return False, [], ""
    needed = bool(parsed.get("needed"))
    reason = str(parsed.get("reason") or "")[:300]
    raw_qs = parsed.get("questions") or []
    cleaned: list[dict[str, str]] = []
    if needed and isinstance(raw_qs, list):
        for i, item in enumerate(raw_qs[:3]):
            if isinstance(item, dict) and item.get("prompt"):
                cleaned.append(
                    {
                        "id": str(item.get("id") or f"gap_{i+1}")[:80],
                        "prompt": str(item["prompt"]).strip()[:300],
                    }
                )
    if needed and not cleaned:
        needed = False
    return needed, cleaned, reason


_SHOT_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "success_story": [
        {"id": "before", "label": "Before / problem context (rack, desk, site)"},
        {"id": "team_client", "label": "Team with client (or anonymized stand-in)"},
        {"id": "finished", "label": "Close-up of finished work / outcome"},
        {"id": "detail", "label": "Detail shot that tells the story without PII"},
    ],
    "personal_achievement": [
        {"id": "moment", "label": "The achievement moment (certificate, stage, desk)"},
        {"id": "team", "label": "You with mentors / team (optional)"},
        {"id": "craft", "label": "Close-up of the craft / work product"},
    ],
    "educational": [
        {"id": "visual", "label": "Simple diagram or whiteboard takeaway"},
        {"id": "context", "label": "Real-world context photo (no sensitive screens)"},
    ],
}


def _serialize_session(row: CaptureSession, *, photos: list[dict] | None = None) -> dict:
    return {
        "id": str(row.id),
        "content_type": row.content_type,
        "photo_mode": row.photo_mode,
        "status": row.status,
        "title": row.title,
        "raw_text": row.raw_text or "",
        "follow_up_questions": row.follow_up_questions_json or [],
        "follow_up_answers": row.follow_up_answers_json or {},
        "shot_list": row.shot_list_json or [],
        "draft_id": str(row.draft_id) if row.draft_id else None,
        "photos": photos or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def _get_session(
    session: AsyncSession, org_id: uuid.UUID, session_id: uuid.UUID
) -> CaptureSession:
    row = (
        await session.execute(
            select(CaptureSession).where(
                CaptureSession.id == session_id,
                CaptureSession.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("CaptureSession", str(session_id))
    return row


async def _photo_items(
    session: AsyncSession, org_id: uuid.UUID, session_id: uuid.UUID
) -> list[dict]:
    delivery = get_delivery_strategy()
    rows = (
        await session.execute(
            select(CaptureAsset)
            .where(
                CaptureAsset.session_id == session_id,
                CaptureAsset.organization_id == org_id,
                CaptureAsset.kind == "photo",
            )
            .order_by(CaptureAsset.created_at.asc())
        )
    ).scalars().all()
    items = []
    for a in rows:
        desc = delivery.resolve(a.object_key, content_type=a.mime_type or "image/jpeg")
        items.append(
            {
                "id": str(a.id),
                "object_key": a.object_key,
                "url": desc.url,
                "mime_type": a.mime_type,
            }
        )
    return items


class CreateCaptureSessionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        org_id: uuid.UUID,
        *,
        content_type: str,
        photo_mode: str = PhotoMode.NONE,
        title: str | None = None,
    ) -> dict:
        if content_type not in _ALLOWED_TYPES:
            raise ValidationError(f"Unsupported content_type: {content_type}")
        if photo_mode not in {m.value for m in PhotoMode}:
            raise ValidationError(f"Unsupported photo_mode: {photo_mode}")
        row = CaptureSession(
            organization_id=org_id,
            content_type=content_type,
            photo_mode=photo_mode,
            status="intake",
            title=title,
        )
        self._session.add(row)
        await self._session.flush()
        return _serialize_session(row)


class GetCaptureSessionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID, session_id: uuid.UUID) -> dict:
        row = await _get_session(self._session, org_id, session_id)
        photos = await _photo_items(self._session, org_id, session_id)
        return _serialize_session(row, photos=photos)


class SaveCaptureTextUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        *,
        text: str,
        title: str | None = None,
        photo_mode: str | None = None,
    ) -> dict:
        row = await _get_session(self._session, org_id, session_id)
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValidationError("Story text is required")
        if len(cleaned) > 20000:
            raise ValidationError("Story text is too long")
        row.raw_text = cleaned
        if title is not None:
            row.title = title.strip()[:500] or None
        if photo_mode is not None:
            if photo_mode not in {m.value for m in PhotoMode}:
                raise ValidationError(f"Unsupported photo_mode: {photo_mode}")
            row.photo_mode = photo_mode
            if photo_mode == PhotoMode.JOB_PLANNED and not row.shot_list_json:
                row.shot_list_json = list(
                    _SHOT_TEMPLATES.get(row.content_type, _SHOT_TEMPLATES["success_story"])
                )
        if row.status == "intake":
            row.status = "story"
        await self._session.flush()
        photos = await _photo_items(self._session, org_id, session_id)
        return _serialize_session(row, photos=photos)


class CaptureVoiceUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._storage = get_storage_provider()
        self._stt = get_transcription_provider()
        self._translator = get_translation_provider()

    async def execute(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        *,
        audio_bytes: bytes,
        content_type: str = "audio/webm",
        append: bool = False,
    ) -> dict:
        row = await _get_session(self._session, org_id, session_id)
        if not audio_bytes:
            raise ValidationError("Audio is empty")
        if len(audio_bytes) > 25 * 1024 * 1024:
            raise ValidationError("Audio file is too large (max 25MB)")

        ext = "webm"
        if "ogg" in content_type:
            ext = "ogg"
        elif "wav" in content_type or audio_bytes[:4] == b"RIFF":
            ext = "wav"
        elif "mp4" in content_type or "m4a" in content_type:
            ext = "m4a"
        elif "mpeg" in content_type or "mp3" in content_type:
            ext = "mp3"

        asset_id = uuid.uuid4()
        key = f"{org_id}/capture/{session_id}/audio/{asset_id}.{ext}"
        stored = self._storage.put_bytes(key, audio_bytes, content_type=content_type)

        # Prefer WAV (browser converts MediaRecorder webm → 16kHz wav for Azure REST)
        if audio_bytes[:4] == b"RIFF":
            stt_content_type = "audio/wav"
            content_type = "audio/wav"
        elif "webm" in (content_type or "").lower():
            stt_content_type = (
                content_type
                if "codecs" in (content_type or "").lower()
                else "audio/webm; codecs=opus"
            )
        else:
            stt_content_type = content_type

        result = await self._stt.transcribe(
            audio_bytes, content_type=stt_content_type
        )
        original = result.text.strip()
        translation = await self._translator.translate_if_needed(
            original, target_language="en"
        )
        transcript = translation.text.strip() or original

        asset = CaptureAsset(
            id=asset_id,
            organization_id=org_id,
            session_id=session_id,
            kind="audio",
            object_key=stored.storage_key,
            mime_type=content_type,
            file_size_bytes=stored.size_bytes,
            transcript=transcript,
            metadata_json={
                "provider": result.provider,
                "locale": result.locale,
                "original_transcript": original,
                "translated": translation.translated,
                "source_language": translation.source_language,
                "translation_provider": translation.provider,
            },
        )
        self._session.add(asset)

        if append and row.raw_text:
            row.raw_text = f"{row.raw_text.rstrip()}\n\n{transcript}"
        else:
            row.raw_text = transcript
        if row.status == "intake":
            row.status = "story"
        await self._session.flush()
        photos = await _photo_items(self._session, org_id, session_id)
        payload = _serialize_session(row, photos=photos)
        payload["transcript"] = transcript
        payload["original_transcript"] = original
        payload["translated"] = translation.translated
        payload["source_language"] = translation.source_language
        payload["transcription_provider"] = result.provider
        payload["translation_provider"] = translation.provider
        payload["asset_id"] = str(asset_id)
        return payload


class SuggestFollowUpsUseCase:
    """Ask follow-ups only when the story lacks clarity for a LinkedIn draft.

    Returns needed=false + empty questions when the capture is already strong enough.
    When needed, questions are AI-generated from gaps (max 3) — never a fixed checklist.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID, session_id: uuid.UUID) -> dict:
        row = await _get_session(self._session, org_id, session_id)
        story = (row.raw_text or "").strip()
        if not story:
            raise ValidationError("Add your story before follow-up questions")

        needed = False
        questions: list[dict[str, str]] = []
        reason = ""

        try:
            orch = AIOrchestratorFactory.create()
            prompt = (
                "You help draft LinkedIn posts from a practitioner's capture story.\n"
                "Decide if the story already has enough clarity to write a strong post, "
                "or if 1–3 short follow-up questions are required.\n\n"
                "Ask follow-ups ONLY when something critical is missing or unclear, e.g.:\n"
                "- Vague / too short / hard to understand\n"
                "- No concrete outcome, lesson, or who benefited\n"
                "- Ambiguous names/details that need anonymizing guidance\n"
                "- Missing the 'so what' for peers\n\n"
                "Do NOT ask generic interview questions if the story is already clear.\n"
                "Do NOT ask more than 3 questions. Prefer 0 when possible.\n"
                "Questions must be specific to THIS story (not a static template).\n\n"
                f"Content type: {row.content_type}\n"
                f"Title: {row.title or '(none)'}\n"
                f"Story:\n{story[:3500]}\n\n"
                "Return ONLY JSON:\n"
                '{"needed": false|true, "reason": "short why", '
                '"questions": [{"id":"snake_case","prompt":"..."}]}\n'
                "If needed is false, questions must be []."
            )
            completion = await orch.complete(
                capability="analysis",
                prompt=prompt,
                organization_id=org_id,
                response_format="json",
            )
            needed, questions, reason = _parse_follow_up_payload(completion.text or "")
        except Exception:
            logger.debug("Follow-up LLM analysis failed; using heuristic", exc_info=True)
            if _story_looks_sufficient(story):
                needed, questions, reason = False, [], "Story looks complete enough"
            else:
                needed, questions, reason = (
                    True,
                    list(_THIN_STORY_FALLBACK),
                    "Story needs more concrete detail",
                )

        row.follow_up_questions_json = questions
        meta = dict(row.metadata_json or {})
        meta["follow_ups_needed"] = needed
        meta["follow_ups_reason"] = reason
        row.metadata_json = meta
        if row.status in ("intake", "story"):
            row.status = "follow_ups" if needed else "photos"
        await self._session.flush()
        return {
            "session_id": str(row.id),
            "needed": needed,
            "reason": reason,
            "questions": questions,
        }


class SaveFollowUpsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        *,
        answers: dict[str, str],
    ) -> dict:
        row = await _get_session(self._session, org_id, session_id)
        cleaned: dict[str, str] = {}
        for key, value in (answers or {}).items():
            if not isinstance(key, str):
                continue
            text = str(value or "").strip()
            if text:
                cleaned[key[:80]] = text[:5000]
        row.follow_up_answers_json = cleaned
        if row.status in ("intake", "story", "follow_ups"):
            row.status = "photos"
        await self._session.flush()
        photos = await _photo_items(self._session, org_id, session_id)
        return _serialize_session(row, photos=photos)


class UpdatePhotoModeUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        *,
        photo_mode: str,
    ) -> dict:
        row = await _get_session(self._session, org_id, session_id)
        if photo_mode not in {m.value for m in PhotoMode}:
            raise ValidationError(f"Unsupported photo_mode: {photo_mode}")
        row.photo_mode = photo_mode
        if photo_mode == PhotoMode.JOB_PLANNED:
            row.shot_list_json = list(
                _SHOT_TEMPLATES.get(row.content_type, _SHOT_TEMPLATES["success_story"])
            )
        elif photo_mode == PhotoMode.NONE:
            row.shot_list_json = []
        await self._session.flush()
        photos = await _photo_items(self._session, org_id, session_id)
        return _serialize_session(row, photos=photos)


class UploadCapturePhotosUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._storage = get_storage_provider()

    async def execute(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        *,
        files: list[tuple[bytes, str, str]],
    ) -> dict:
        """files: list of (bytes, filename, content_type)."""
        row = await _get_session(self._session, org_id, session_id)
        if not files:
            raise ValidationError("No photos uploaded")
        if len(files) > 8:
            raise ValidationError("Maximum 8 photos per upload")

        created = []
        for data, filename, content_type in files:
            if not data:
                continue
            if len(data) > 15 * 1024 * 1024:
                raise ValidationError(f"Photo too large: {filename}")
            mime = content_type or "image/jpeg"
            if not mime.startswith("image/"):
                raise ValidationError(f"Not an image: {filename}")
            ext = "jpg"
            if "png" in mime:
                ext = "png"
            elif "webp" in mime:
                ext = "webp"
            elif "heic" in mime or "heif" in mime:
                ext = "heic"
            asset_id = uuid.uuid4()
            key = f"{org_id}/capture/{session_id}/photos/{asset_id}.{ext}"
            stored = self._storage.put_bytes(key, data, content_type=mime)
            asset = CaptureAsset(
                id=asset_id,
                organization_id=org_id,
                session_id=session_id,
                kind="photo",
                object_key=stored.storage_key,
                mime_type=mime,
                file_size_bytes=stored.size_bytes,
                metadata_json={"filename": filename[:200]},
            )
            self._session.add(asset)
            created.append(str(asset_id))

        if row.photo_mode in (PhotoMode.NONE, "none"):
            row.photo_mode = PhotoMode.HAS_PHOTOS
        await self._session.flush()
        photos = await _photo_items(self._session, org_id, session_id)
        payload = _serialize_session(row, photos=photos)
        payload["uploaded_ids"] = created
        return payload


class GenerateFromCaptureUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._generator = ContentGenerator(session, AIOrchestratorFactory.create())
        self._claims = ClaimsGuard(session)

    async def execute(self, org_id: uuid.UUID, session_id: uuid.UUID) -> dict:
        row = await _get_session(self._session, org_id, session_id)
        story = (row.raw_text or "").strip()
        if not story:
            raise ValidationError("Add your story before generating a draft")

        row.status = "generating"
        await self._session.flush()

        answers = row.follow_up_answers_json if isinstance(row.follow_up_answers_json, dict) else {}
        generated = await self._generator.generate_from_capture(
            org_id=org_id,
            content_type=row.content_type,
            title=row.title or "",
            story=story,
            follow_up_answers=answers,
        )

        if generated.get("validation_passed") is False:
            row.status = "photos"
            await self._session.flush()
            errors = generated.get("errors") or ["validation failed"]
            raise ValidationError(
                f"Draft generation failed validation: {'; '.join(str(e) for e in errors)}"
            )

        source_parts = [story]
        for k, v in answers.items():
            source_parts.append(f"{k}: {v}")
        source_text = "\n".join(source_parts)
        body = generated.get("body", "")
        claims_result = await self._claims.verify(
            org_id=org_id, text=body, source_text=source_text
        )

        draft = Draft(
            article_id=None,
            organization_id=org_id,
            content_type=row.content_type,
            status=DraftStatus.PENDING_REVIEW,
            generated_text=body,
            edited_text=None,
            hook=generated.get("hook", ""),
            cta=generated.get("cta", ""),
            hashtags_json=generated.get("hashtags", []),
            metadata_json={
                "capture": True,
                "capture_session_id": str(row.id),
                "plan_origin": True,
                "origin": PLAN_ORIGIN,
                "photo_mode": row.photo_mode,
                "shot_list": row.shot_list_json or [],
                "prefer_real_photos": row.photo_mode
                in (PhotoMode.HAS_PHOTOS, PhotoMode.TAKE_NOW, "has_photos", "take_now"),
                "source": "capture_session",
                "claims_guard": {
                    "passed": claims_result.passed,
                    "flagged": claims_result.flagged_claims,
                },
                "content_type": row.content_type,
                "validation_passed": True,
                "quality_score": generated.get("quality_score"),
                "confidence_score": generated.get("confidence_score"),
                "replay_id": generated.get("replay_id"),
                "draft": generated.get("draft"),
                "source_text": source_text[:2000],
            },
            version=1,
        )
        self._session.add(draft)
        await self._session.flush()

        # Attach uploaded photos as MediaAssets on the draft
        photo_assets = (
            await self._session.execute(
                select(CaptureAsset).where(
                    CaptureAsset.session_id == session_id,
                    CaptureAsset.organization_id == org_id,
                    CaptureAsset.kind == "photo",
                )
            )
        ).scalars().all()
        for a in photo_assets:
            self._session.add(
                MediaAsset(
                    organization_id=org_id,
                    draft_id=draft.id,
                    kind="capture_photo",
                    object_key=a.object_key,
                    version=1,
                    file_size_bytes=a.file_size_bytes,
                    mime_type=a.mime_type,
                    exif_stripped=False,
                )
            )

        row.draft_id = draft.id
        row.status = "completed"
        await self._session.flush()

        return {
            "id": str(draft.id),
            "session_id": str(row.id),
            "content_type": draft.content_type,
            "status": draft.status,
            "hook": draft.hook,
            "photo_mode": row.photo_mode,
            "prefer_real_photos": bool(
                (draft.metadata_json or {}).get("prefer_real_photos")
            ),
            "photo_count": len(photo_assets),
        }
