"""Image generation routes — RBAC enforced."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.envelope import success_response
from app.api.schemas.images import GenerateImagesRequest
from app.core.constants import MembershipRole
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.security import require_role
from app.infrastructure.postgres import get_async_session
from app.infrastructure.postgres.models.carousel import MediaAsset
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.imaging import ImageJob
from app.infrastructure.storage.factory import get_delivery_strategy
from app.modules.auth.domain.entities import AuthenticatedUser
from app.modules.image.application.factory import VisualIntelligenceFactory
from app.modules.image.application.gallery_assets import (
    job_id_and_role_from_object_key,
    media_belongs_to_jobs,
    select_gallery_media,
)
from app.modules.image.application.queue_generation import (
    clear_inflight,
    is_inflight,
    queue_async_image_generation,
    register_image_runner,
    schedule_image_job,
    set_draft_image_gen,
)
from app.modules.image.application.workflow import VisualWorkflow

router = APIRouter(tags=["images"])
logger = get_logger(__name__)

# Process-scoped engine respects IMAGE_PROVIDER (openai / gemini / comfyui)
_engine = VisualIntelligenceFactory.create()

_ACTIVE_JOB_STATUSES = frozenset(
    {"pending", "running", "queued", "generating", "upscaling", "quality_check", "typography"}
)
_STALE_AFTER = timedelta(minutes=20)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _job_age(job: ImageJob) -> timedelta:
    created = job.created_at
    if created is None:
        return timedelta(0)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return _utc_now() - created


def _is_batch_job(job: ImageJob) -> bool:
    meta = job.generation_metadata_json or {}
    return bool(meta.get("batch") or meta.get("async"))


# Back-compat aliases for this module
_set_draft_image_gen = set_draft_image_gen
_schedule_image_job = schedule_image_job


@router.get("/drafts/{draft_id}/images")
async def list_draft_images(
    draft_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """List generated illustration assets for a draft (for draft-page gallery)."""
    org_id = current_user.organization_id
    draft = await session.get(Draft, draft_id)
    if draft is None or draft.organization_id != org_id:
        raise NotFoundError("Draft", str(draft_id))

    delivery = get_delivery_strategy()
    media_rows = (
        await session.execute(
            select(MediaAsset)
            .where(
                MediaAsset.organization_id == org_id,
                MediaAsset.draft_id == draft_id,
                MediaAsset.kind.in_(("generated_illustration", "capture_photo")),
            )
            .order_by(MediaAsset.created_at.desc())
        )
    ).scalars().all()
    # Prefer optimized over original for the same job (legacy dual-persist).
    # Keep capture photos first so real uploads surface ahead of AI images.
    capture_rows = [m for m in media_rows if m.kind == "capture_photo"]
    ai_rows = select_gallery_media([m for m in media_rows if m.kind == "generated_illustration"])
    media_rows = list(capture_rows) + list(ai_rows)

    items: list[dict] = []
    for m in media_rows:
        desc = delivery.resolve(m.object_key, content_type=m.mime_type or "image/png")
        items.append(
            {
                "id": str(m.id),
                "object_key": m.object_key,
                "url": desc.url,
                "width": m.width,
                "height": m.height,
                "mime_type": m.mime_type or "image/png",
                "source": "upload" if m.kind == "capture_photo" else "ai",
                "kind": m.kind,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )

    jobs = (
        await session.execute(
            select(ImageJob)
            .where(ImageJob.organization_id == org_id, ImageJob.draft_id == draft_id)
            .order_by(ImageJob.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    provider_by_job_id = {str(j.id): j.provider for j in jobs if j.provider}
    for item in items:
        job_id, _role = job_id_and_role_from_object_key(item.get("object_key") or "")
        item["provider"] = provider_by_job_id.get(job_id or "")

    # After uvicorn --reload (or pre-commit race), batch rows stay pending/running.
    # Never-started jobs are re-dispatched; long-running workers are expired.
    for job in jobs:
        if job.status not in _ACTIVE_JOB_STATUSES:
            continue
        meta = dict(job.generation_metadata_json or {})
        phase = str(meta.get("phase") or "")
        never_started = job.status in {"pending", "queued"} and phase in {"", "queued"}
        age = _job_age(job)

        if never_started and _is_batch_job(job) and not is_inflight(job.id):
            for other in jobs:
                if (
                    other.id != job.id
                    and other.status in _ACTIVE_JOB_STATUSES
                    and not _is_batch_job(other)
                ):
                    other.status = "failed"
                    other.error_message = "Superseded after worker restart"
            count = int(meta.get("requested_count") or 1)
            guidance = meta.get("guidance")
            guidance_s = str(guidance).strip() if guidance else None
            meta["recovered_at"] = _utc_now().isoformat()
            meta["recovery"] = "list_redispatch"
            job.generation_metadata_json = meta
            logger.info(
                "Re-dispatching never-started image batch draft_id=%s batch_id=%s age_s=%.0f",
                draft_id,
                job.id,
                age.total_seconds(),
            )
            _set_draft_image_gen(
                draft, status="running", batch_job_id=job.id, count=count
            )
            _schedule_image_job(org_id, draft_id, count, job.id, guidance_s)
            continue

        if age > _STALE_AFTER:
            job.status = "failed"
            job.error_message = (job.error_message or "Timed out after 20 minutes")[:1000]
            meta["phase"] = "failed"
            meta["stale"] = True
            job.generation_metadata_json = meta
            if _is_batch_job(job):
                _set_draft_image_gen(
                    draft, status="failed", batch_job_id=job.id, error=job.error_message
                )
            clear_inflight(job.id)
            continue

        if _is_batch_job(job) and not is_inflight(job.id) and age > timedelta(seconds=45):
            # Running/queued but worker died mid-flight — retry once.
            count = int(meta.get("requested_count") or 1)
            guidance = meta.get("guidance")
            guidance_s = str(guidance).strip() if guidance else None
            logger.info(
                "Re-dispatching abandoned image batch draft_id=%s batch_id=%s",
                draft_id,
                job.id,
            )
            _set_draft_image_gen(
                draft, status="running", batch_job_id=job.id, count=count
            )
            _schedule_image_job(org_id, draft_id, count, job.id, guidance_s)

    await session.flush()

    job_summary = [
        {
            "job_id": str(j.id),
            "status": j.status,
            "provider": j.provider,
            "quality_score": j.quality_score,
            "error": j.error_message,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "metadata": j.generation_metadata_json,
        }
        for j in jobs
    ]
    # Only batch controllers drive the "generating" UI flag (not per-variant rows).
    active_batches = [
        j
        for j in jobs
        if j.status in _ACTIVE_JOB_STATUSES and _is_batch_job(j)
    ]
    draft_ig = (draft.metadata_json or {}).get("image_generation") or {}
    draft_running = str(draft_ig.get("status") or "") == "running"
    if draft_running and not active_batches:
        # Metadata left "running" after a completed/failed batch — don't spin forever
        _set_draft_image_gen(draft, status="idle")
        draft_running = False

    return success_response(
        {
            "items": items,
            "jobs": job_summary,
            "count": len(items),
            "generating": len(active_batches) > 0 or draft_running,
            "active_jobs": len(active_batches),
        },
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post("/drafts/{draft_id}/images/generate")
async def generate_image(
    draft_id: uuid.UUID,
    request: Request,
    body: GenerateImagesRequest | None = None,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Queue image generation in the background — safe to leave the page."""
    org_id = current_user.organization_id
    draft = await session.get(Draft, draft_id)
    if draft is None or draft.organization_id != org_id:
        raise NotFoundError("Draft", str(draft_id))

    payload = body or GenerateImagesRequest()
    queued = await queue_async_image_generation(
        session,
        org_id=org_id,
        draft_id=draft_id,
        count=payload.count,
        guidance=(payload.guidance or "").strip() or None,
        reason="manual",
        provider=(payload.provider or "").strip() or None,
        providers=payload.providers,
    )
    # Commit so after_commit schedules the worker against a visible ImageJob row.
    await session.commit()

    return success_response(
        {
            **queued,
            "message": "Image generation started in the background. You can leave this page.",
        },
        request_id=getattr(request.state, "request_id", ""),
    )


async def _inline_generate_images(
    org_id: uuid.UUID,
    draft_id: uuid.UUID,
    count: int,
    batch_job_id: uuid.UUID,
    guidance: str | None = None,
    provider: str | None = None,
    providers: list[str] | None = None,
) -> None:
    """Run VisualWorkflow in a standalone session so the HTTP request can return."""
    import asyncio

    from app.infrastructure.postgres.session import async_session_factory

    try:
        async with async_session_factory() as session:
            batch = None
            for attempt in range(15):
                batch = await session.get(ImageJob, batch_job_id)
                if batch is not None:
                    break
                # Commit race safety net (should be rare after after_commit scheduling).
                await asyncio.sleep(0.2)
            if batch is None:
                logger.error(
                    "Image batch missing after wait batch_id=%s draft_id=%s — aborting",
                    batch_job_id,
                    draft_id,
                )
                return
            if batch.status in {"completed", "failed", "complete"}:
                return

            batch.status = "running"
            meta = dict(batch.generation_metadata_json or {})
            meta["phase"] = "running"
            batch.generation_metadata_json = meta
            draft = await session.get(Draft, draft_id)
            if draft is not None:
                _set_draft_image_gen(
                    draft, status="running", batch_job_id=batch_job_id, count=count
                )
            await session.commit()

            try:
                workflow = VisualWorkflow(session, engine=_engine)
                result = await workflow.execute(
                    org_id,
                    draft_id,
                    count=count,
                    guidance=guidance,
                    provider=provider,
                    providers=providers,
                )
                await session.commit()

                batch = await session.get(ImageJob, batch_job_id)
                draft_status = "completed"
                batch_error: str | None = None
                if batch is not None:
                    child_jobs = [
                        j for j in (result.get("jobs") or []) if isinstance(j, dict)
                    ]
                    success_statuses = {"completed", "complete"}
                    fail_statuses = {
                        "failed",
                        "policy_rejected",
                        "validation_failed",
                    }
                    any_ok = any(
                        str(j.get("status") or "") in success_statuses for j in child_jobs
                    )
                    all_failed = bool(child_jobs) and all(
                        str(j.get("status") or "") in fail_statuses for j in child_jobs
                    )
                    costs = [
                        float(j["cost_estimate"])
                        for j in child_jobs
                        if j.get("cost_estimate") is not None
                    ]
                    latencies = [
                        int(j["latency_ms"])
                        for j in child_jobs
                        if j.get("latency_ms") is not None
                    ]
                    providers = [str(j["provider"]) for j in child_jobs if j.get("provider")]
                    models = [str(j["model"]) for j in child_jobs if j.get("model")]
                    if providers:
                        batch.provider = providers[0]
                    if models:
                        batch.model = models[0]
                    if latencies:
                        batch.latency_ms = max(latencies)

                    # Real API cost lives on child jobs only. Batch stores a display total in
                    # metadata so Jobs/Analytics do not double-count the same generation.
                    batch.cost_estimate = None
                    meta = dict(batch.generation_metadata_json or {})
                    meta["job_ids"] = [j.get("job_id") for j in child_jobs]
                    meta["providers"] = providers
                    if costs:
                        meta["total_cost_estimate"] = round(sum(costs), 6)
                    meta["result_count"] = result.get("count")
                    meta["child_statuses"] = [j.get("status") for j in child_jobs]

                    if all_failed or not any_ok:
                        batch.status = "failed"
                        err_bits = []
                        for j in child_jobs:
                            if j.get("error"):
                                err_bits.append(str(j["error"]))
                            codes = (j.get("metadata") or {}).get("reason_codes") or []
                            if codes:
                                err_bits.append(",".join(str(c) for c in codes))
                        batch.error_message = (
                            "; ".join(err_bits) or "image generation produced no assets"
                        )[:1000]
                        meta["phase"] = "failed"
                        draft_status = "failed"
                        batch_error = batch.error_message
                    else:
                        batch.status = "completed"
                        batch.error_message = None
                        meta["phase"] = "completed"
                        draft_status = "completed"
                        # Replace gallery: drop prior illustrations not from this batch.
                        keep_ids = {
                            str(j.get("job_id"))
                            for j in child_jobs
                            if j.get("job_id")
                            and str(j.get("status") or "") in success_statuses
                        }
                        if keep_ids:
                            prior = (
                                await session.execute(
                                    select(MediaAsset).where(
                                        MediaAsset.organization_id == org_id,
                                        MediaAsset.draft_id == draft_id,
                                        MediaAsset.kind == "generated_illustration",
                                    )
                                )
                            ).scalars().all()
                            for m in prior:
                                if not media_belongs_to_jobs(m.object_key, keep_ids):
                                    await session.delete(m)
                    batch.generation_metadata_json = meta
                draft = await session.get(Draft, draft_id)
                if draft is not None:
                    _set_draft_image_gen(
                        draft,
                        status=draft_status,
                        batch_job_id=batch_job_id,
                        count=int(result.get("count") or count),
                        error=batch_error,
                    )
                await session.commit()
                logger.info(
                    "Async image generation completed draft_id=%s batch_id=%s",
                    draft_id,
                    batch_job_id,
                )
            except Exception as exc:  # noqa: BLE001 — background task must not crash process
                logger.exception(
                    "Async image generation failed draft_id=%s batch_id=%s",
                    draft_id,
                    batch_job_id,
                )
                await session.rollback()
                batch = await session.get(ImageJob, batch_job_id)
                if batch is not None:
                    batch.status = "failed"
                    batch.error_message = str(exc)[:1000]
                    meta = dict(batch.generation_metadata_json or {})
                    meta["phase"] = "failed"
                    batch.generation_metadata_json = meta
                draft = await session.get(Draft, draft_id)
                if draft is not None:
                    _set_draft_image_gen(
                        draft,
                        status="failed",
                        batch_job_id=batch_job_id,
                        error=str(exc),
                    )
                await session.commit()
    finally:
        clear_inflight(batch_job_id)


register_image_runner(_inline_generate_images)


@router.post("/images/jobs/{job_id}/replay")
async def replay_image_job(
    job_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.EDITOR)),
) -> dict:
    result = await _engine.replay(job_id=str(job_id))
    return success_response(result.to_dict(), request_id=getattr(request.state, "request_id", ""))


@router.get("/images/jobs/{job_id}/similar")
async def similar_images(
    job_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
) -> dict:
    hits = _engine.embedding_service.similar(str(job_id))
    return success_response(
        {"job_id": str(job_id), "similar": [{"job_id": j, "score": s} for j, s in hits]},
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/images/jobs/{job_id}/duplicates")
async def duplicate_images(
    job_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
) -> dict:
    hits = _engine.embedding_service.duplicates(str(job_id))
    return success_response(
        {"job_id": str(job_id), "duplicates": [{"job_id": j, "score": s} for j, s in hits]},
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/images/jobs/{job_id}/recommend")
async def recommend_images(
    job_id: uuid.UUID,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_role(MembershipRole.VIEWER)),
) -> dict:
    hits = _engine.embedding_service.recommend(str(job_id))
    return success_response(
        {"job_id": str(job_id), "recommendations": [{"job_id": j, "score": s} for j, s in hits]},
        request_id=getattr(request.state, "request_id", ""),
    )
