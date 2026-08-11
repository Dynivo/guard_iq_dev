"""Jobs application use cases — no raw SQL in routes."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.infrastructure.postgres.models.imaging import ImageJob
from app.infrastructure.postgres.models.jobs import Job


class ListJobsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(Job)
                .where(Job.organization_id == org_id)
                .order_by(Job.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        items: list[dict[str, Any]] = [
            {
                "id": str(j.id),
                "type": j.job_type,
                "status": j.status,
                "progress": _progress_for_status(j.status),
                "error_message": j.last_error,
                "attempts": j.attempts,
                "payload": j.payload_json,
                "result": j.result_json,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in rows
        ]

        # Image generation: show one row per user request (batch), not each child render.
        # Child jobs still hold the real per-image cost for analytics.
        image_rows = (
            await self._session.execute(
                select(ImageJob)
                .where(
                    ImageJob.organization_id == org_id,
                )
                .order_by(ImageJob.created_at.desc())
                .limit(limit * 3)
            )
        ).scalars().all()
        for img in image_rows:
            meta = img.generation_metadata_json or {}
            is_batch = bool(meta.get("batch") or meta.get("async"))
            is_child = "variant_index" in meta and not is_batch
            if is_child:
                continue
            if not is_batch and not img.provider and img.status not in {
                "pending",
                "running",
                "queued",
                "generating",
            }:
                continue
            items.append(
                {
                    "id": str(img.id),
                    "type": "image_generate",
                    "status": img.status,
                    "progress": _progress_for_status(img.status),
                    "error_message": img.error_message,
                    "attempts": img.retry_count or 0,
                    "payload": {
                        "draft_id": str(img.draft_id) if img.draft_id else None,
                        "provider": img.provider,
                        "model": img.model,
                        "cost_estimate": img.cost_estimate
                        if img.cost_estimate is not None
                        else meta.get("total_cost_estimate"),
                        "requested_count": meta.get("requested_count")
                        or meta.get("result_count")
                        or 1,
                        "metadata": meta,
                    },
                    "result": {
                        "quality_score": img.quality_score,
                        "latency_ms": img.latency_ms,
                    },
                    "created_at": img.created_at.isoformat() if img.created_at else None,
                }
            )

        items.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return items[:limit]


class GetJobUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, org_id: uuid.UUID, job_id: uuid.UUID) -> dict[str, Any]:
        job = await self._session.get(Job, job_id)
        if job is not None and job.organization_id == org_id:
            return {
                "id": str(job.id),
                "type": job.job_type,
                "status": job.status,
                "progress": _progress_for_status(job.status),
                "error_message": job.last_error,
                "attempts": job.attempts,
                "payload": job.payload_json,
                "result": job.result_json,
            }
        img = await self._session.get(ImageJob, job_id)
        if img is None or img.organization_id != org_id:
            raise NotFoundError("Job", str(job_id))
        meta = img.generation_metadata_json or {}
        return {
            "id": str(img.id),
            "type": "image_generate",
            "status": img.status,
            "progress": _progress_for_status(img.status),
            "error_message": img.error_message,
            "attempts": img.retry_count or 0,
            "payload": {
                "draft_id": str(img.draft_id) if img.draft_id else None,
                "provider": img.provider,
                "model": img.model,
                "cost_estimate": img.cost_estimate,
                "metadata": meta,
            },
            "result": {
                "quality_score": img.quality_score,
                "latency_ms": img.latency_ms,
            },
        }


def _progress_for_status(status: str) -> int:
    mapping = {
        "pending": 0,
        "queued": 0,
        "running": 50,
        "generating": 50,
        "retrying": 40,
        "completed": 100,
        "complete": 100,
        "failed": 100,
    }
    return mapping.get(status, 0)
