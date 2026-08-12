"""Queue async image generation for a draft (replaceable; used by routes + draft pipeline)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.logging import get_logger
from app.infrastructure.postgres.models.branding import BrandKit
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.imaging import ImageJob
from app.modules.image.application.count_policy import resolve_image_count

logger = get_logger(__name__)

_inflight_batches: set[uuid.UUID] = set()
# async (org_id, draft_id, count, batch_job_id, guidance, provider, providers) -> None
_ImageRunner = Any
_image_runner: _ImageRunner | None = None


def register_image_runner(runner: _ImageRunner) -> None:
    """Routes register the VisualWorkflow runner at import time (avoids cycles)."""
    global _image_runner
    _image_runner = runner


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def set_draft_image_gen(
    draft: Draft,
    *,
    status: str,
    batch_job_id: uuid.UUID | None = None,
    count: int | None = None,
    error: str | None = None,
) -> None:
    meta = dict(draft.metadata_json or {})
    prev = dict(meta.get("image_generation") or {})
    payload: dict[str, Any] = {
        **prev,
        "status": status,
        "updated_at": _utc_now().isoformat(),
    }
    if batch_job_id is not None:
        payload["batch_job_id"] = str(batch_job_id)
    if count is not None:
        payload["count"] = count
    if status == "running" and "started_at" not in payload:
        payload["started_at"] = _utc_now().isoformat()
    if error:
        payload["error"] = error[:500]
    meta["image_generation"] = payload
    draft.metadata_json = meta
    flag_modified(draft, "metadata_json")


async def load_brand_image_settings(session: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    row = (
        await session.execute(select(BrandKit).where(BrandKit.organization_id == org_id).limit(1))
    ).scalar_one_or_none()
    extra = dict(row.extra_settings or {}) if row else {}
    return {
        "default_image_count": int(extra.get("default_image_count") or 1),
        "auto_generate_image_with_draft": bool(extra.get("auto_generate_image_with_draft")),
        "extra": extra,
    }


def _schedule_after_commit(
    session: AsyncSession,
    org_id: uuid.UUID,
    draft_id: uuid.UUID,
    count: int,
    batch_job_id: uuid.UUID,
    guidance: str | None,
    provider: str | None = None,
    providers: list[str] | None = None,
) -> None:
    """Run the background worker only after the request transaction commits.

    Scheduling before commit races the worker (new session) against an uncommitted
    ImageJob row — the worker sees ``batch is None`` and exits, leaving drafts stuck
    on ``pending`` / ``generating`` forever.
    """
    sync = session.sync_session

    def _on_commit(_sess: Any) -> None:
        logger.info(
            "Scheduling image batch after commit draft_id=%s batch_id=%s",
            draft_id,
            batch_job_id,
        )
        schedule_image_job(org_id, draft_id, count, batch_job_id, guidance, provider, providers)

    event.listen(sync, "after_commit", _on_commit, once=True)


async def queue_async_image_generation(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    draft_id: uuid.UUID,
    count: int | None = None,
    guidance: str | None = None,
    reason: str = "manual",
    provider: str | None = None,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    """Create batch ImageJob and mark draft. Schedules worker after session commit.

    ``providers`` (e.g. ["openai", "gemini"]) generates one variant per
    provider in the same batch, so they land in the gallery together for
    side-by-side comparison — overrides ``count``/``provider`` when set.
    """
    draft = await session.get(Draft, draft_id)
    if draft is None or draft.organization_id != org_id:
        raise ValueError(f"Draft {draft_id} not found for org")

    providers_list = [p.strip() for p in (providers or []) if p and p.strip()] or None

    settings = await load_brand_image_settings(session, org_id)
    image_count = len(providers_list) if providers_list else resolve_image_count(
        count, brand_extra=settings["extra"]
    )
    guidance_s = (guidance or "").strip() or None
    provider_s = (provider or "").strip() or None

    batch = ImageJob(
        organization_id=org_id,
        draft_id=draft_id,
        status="pending",
        generation_metadata_json={
            "phase": "queued",
            "requested_count": image_count,
            "batch": True,
            "async": True,
            "guidance": guidance_s,
            "reason": reason,
            "provider_override": provider_s,
            "providers": providers_list,
        },
    )
    session.add(batch)
    await session.flush()
    set_draft_image_gen(
        draft, status="running", batch_job_id=batch.id, count=image_count
    )
    _schedule_after_commit(
        session, org_id, draft_id, image_count, batch.id, guidance_s, provider_s, providers_list
    )
    logger.info(
        "Queued image generation draft_id=%s batch_id=%s count=%s reason=%s providers=%s",
        draft_id,
        batch.id,
        image_count,
        reason,
        providers_list,
    )
    return {
        "status": "queued",
        "async": True,
        "draft_id": str(draft_id),
        "batch_job_id": str(batch.id),
        "count": image_count,
        "generating": True,
        "reason": reason,
    }


def schedule_image_job(
    org_id: uuid.UUID,
    draft_id: uuid.UUID,
    count: int,
    batch_job_id: uuid.UUID,
    guidance: str | None,
    provider: str | None = None,
    providers: list[str] | None = None,
) -> None:
    if batch_job_id in _inflight_batches:
        return
    if _image_runner is None:
        logger.error("Image runner not registered — cannot schedule batch_id=%s", batch_job_id)
        return
    _inflight_batches.add(batch_job_id)
    runner = _image_runner

    async def _run() -> None:
        try:
            await runner(org_id, draft_id, count, batch_job_id, guidance, provider, providers)
        finally:
            _inflight_batches.discard(batch_job_id)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run(), name=f"images-{draft_id}-{batch_job_id}")
    except RuntimeError:
        _inflight_batches.discard(batch_job_id)
        logger.warning("No running event loop — image job not scheduled batch_id=%s", batch_job_id)


def is_inflight(batch_job_id: uuid.UUID) -> bool:
    return batch_job_id in _inflight_batches


def clear_inflight(batch_job_id: uuid.UUID) -> None:
    _inflight_batches.discard(batch_job_id)
