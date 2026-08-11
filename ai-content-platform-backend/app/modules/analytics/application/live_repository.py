"""Durable analytics from Postgres — survives uvicorn reload."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.ai_ops import LlmCall
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.imaging import ImageJob
from app.infrastructure.postgres.models.jobs import Job


def _exclude_image_batch_wrappers():
    """Batch ImageJob rows mirror child costs — exclude them from usage/cost aggregates."""
    meta = ImageJob.generation_metadata_json
    batch_flag = func.coalesce(meta["batch"].astext, "false")
    return ~batch_flag.in_(("true", "True", "1"))


class LiveAnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def provider_health(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(
                    LlmCall.provider,
                    func.count().label("requests"),
                    func.sum(case((LlmCall.status == "success", 1), else_=0)).label(
                        "successes"
                    ),
                    func.sum(case((LlmCall.status != "success", 1), else_=0)).label(
                        "failures"
                    ),
                    func.coalesce(func.avg(LlmCall.latency_ms), 0).label("avg_latency"),
                )
                .where(
                    (LlmCall.organization_id == org_id) | (LlmCall.organization_id.is_(None))
                )
                .group_by(LlmCall.provider)
            )
        ).all()

        # Also fold image providers that actually ran (skip batch wrapper rows)
        image_rows = (
            await self._session.execute(
                select(
                    ImageJob.provider,
                    func.count().label("requests"),
                    func.sum(
                        case((ImageJob.status.in_(("completed", "complete")), 1), else_=0)
                    ).label("successes"),
                    func.sum(case((ImageJob.status == "failed", 1), else_=0)).label(
                        "failures"
                    ),
                    func.coalesce(func.avg(ImageJob.latency_ms), 0).label("avg_latency"),
                )
                .where(
                    ImageJob.organization_id == org_id,
                    ImageJob.provider.is_not(None),
                    _exclude_image_batch_wrappers(),
                )
                .group_by(ImageJob.provider)
            )
        ).all()

        by_provider: dict[str, dict[str, Any]] = {}
        for provider, requests, successes, failures, avg_latency in list(rows) + list(
            image_rows
        ):
            key = str(provider or "unknown")
            cur = by_provider.setdefault(
                key,
                {
                    "provider": key,
                    "requests": 0,
                    "successes": 0,
                    "failures": 0,
                    "timeouts": 0,
                    "fallbacks": 0,
                    "total_latency_ms": 0.0,
                    "error_classes": {},
                    "status": "observed",
                },
            )
            req = int(requests or 0)
            suc = int(successes or 0)
            fail = int(failures or 0)
            cur["requests"] += req
            cur["successes"] += suc
            cur["failures"] += fail
            cur["total_latency_ms"] += float(avg_latency or 0) * req

        out: list[dict[str, Any]] = []
        for cur in by_provider.values():
            req = int(cur["requests"])
            suc = int(cur["successes"])
            out.append(
                {
                    **cur,
                    "availability": round((suc / req) if req else 0.0, 4),
                    "average_latency_ms": round(
                        (float(cur["total_latency_ms"]) / req) if req else 0.0, 2
                    ),
                }
            )
        return sorted(out, key=lambda r: (-int(r["requests"]), str(r["provider"])))

    async def model_health(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(
                    LlmCall.provider,
                    LlmCall.model,
                    func.count().label("requests"),
                    func.coalesce(func.sum(LlmCall.cost_estimate), 0).label("total_cost"),
                    func.coalesce(func.sum(LlmCall.latency_ms), 0).label("total_latency"),
                    func.coalesce(func.sum(LlmCall.tokens_in), 0).label("tokens_in"),
                    func.coalesce(func.sum(LlmCall.tokens_out), 0).label("tokens_out"),
                )
                .where(
                    (LlmCall.organization_id == org_id) | (LlmCall.organization_id.is_(None))
                )
                .group_by(LlmCall.provider, LlmCall.model)
            )
        ).all()
        out = []
        for provider, model, requests, total_cost, total_latency, tokens_in, tokens_out in rows:
            req = int(requests or 0)
            out.append(
                {
                    "provider": str(provider or "unknown"),
                    "model": str(model or "unknown"),
                    "requests": req,
                    "total_cost": round(float(total_cost or 0), 6),
                    "total_latency_ms": int(total_latency or 0),
                    "average_latency_ms": round((int(total_latency or 0) / req) if req else 0, 2),
                    "tokens_in": int(tokens_in or 0),
                    "tokens_out": int(tokens_out or 0),
                    "cache_hits": 0,
                    "status": "observed",
                }
            )
        return sorted(out, key=lambda r: (-int(r["requests"]), r["provider"], r["model"]))

    async def cost(self, org_id: uuid.UUID) -> dict[str, Any]:
        llm_total = (
            await self._session.execute(
                select(func.coalesce(func.sum(LlmCall.cost_estimate), 0)).where(
                    (LlmCall.organization_id == org_id) | (LlmCall.organization_id.is_(None))
                )
            )
        ).scalar_one()
        image_total = (
            await self._session.execute(
                select(func.coalesce(func.sum(ImageJob.cost_estimate), 0)).where(
                    ImageJob.organization_id == org_id,
                    _exclude_image_batch_wrappers(),
                )
            )
        ).scalar_one()

        by_provider = (
            await self._session.execute(
                select(
                    LlmCall.provider,
                    func.coalesce(func.sum(LlmCall.cost_estimate), 0),
                )
                .where(
                    (LlmCall.organization_id == org_id) | (LlmCall.organization_id.is_(None))
                )
                .group_by(LlmCall.provider)
            )
        ).all()
        usage: dict[str, float] = {
            str(p or "unknown"): round(float(c or 0), 6) for p, c in by_provider
        }
        image_by_provider = (
            await self._session.execute(
                select(
                    ImageJob.provider,
                    func.coalesce(func.sum(ImageJob.cost_estimate), 0),
                )
                .where(
                    ImageJob.organization_id == org_id,
                    ImageJob.provider.is_not(None),
                    _exclude_image_batch_wrappers(),
                )
                .group_by(ImageJob.provider)
            )
        ).all()
        for p, c in image_by_provider:
            key = str(p or "image")
            usage[key] = round(usage.get(key, 0) + float(c or 0), 6)
        # Orphan image costs without provider
        orphan_img = float(image_total or 0) - sum(float(c or 0) for _, c in image_by_provider)
        if orphan_img > 0.0000001:
            usage["image_generation"] = round(usage.get("image_generation", 0) + orphan_img, 6)

        return {
            "organization_id": str(org_id),
            "total": round(float(llm_total or 0) + float(image_total or 0), 6),
            "usage": usage,
            "currency": "USD",
            "source": "live_db",
        }

    async def usage(self, org_id: uuid.UUID) -> dict[str, Any]:
        cost = await self.cost(org_id)
        call_count = (
            await self._session.execute(
                select(func.count()).select_from(LlmCall).where(
                    (LlmCall.organization_id == org_id) | (LlmCall.organization_id.is_(None))
                )
            )
        ).scalar_one()
        image_count = (
            await self._session.execute(
                select(func.count())
                .select_from(ImageJob)
                .where(
                    ImageJob.organization_id == org_id,
                    ImageJob.status.in_(("completed", "complete")),
                    _exclude_image_batch_wrappers(),
                )
            )
        ).scalar_one()
        draft_count = (
            await self._session.execute(
                select(func.count()).select_from(Draft).where(Draft.organization_id == org_id)
            )
        ).scalar_one()
        return {
            "organization_id": str(org_id),
            "usage": cost.get("usage") or {},
            "signals": [
                {"name": "llm_calls", "value": int(call_count or 0)},
                {"name": "images_completed", "value": int(image_count or 0)},
                {"name": "drafts", "value": int(draft_count or 0)},
            ],
            "source": "live_db",
        }

    async def workflow_health(self, org_id: uuid.UUID) -> dict[str, Any]:
        job_rows = (
            await self._session.execute(
                select(Job.status, func.count())
                .where(Job.organization_id == org_id)
                .group_by(Job.status)
            )
        ).all()
        image_rows = (
            await self._session.execute(
                select(ImageJob.status, func.count())
                .where(ImageJob.organization_id == org_id)
                .group_by(ImageJob.status)
            )
        ).all()
        counts: dict[str, int] = defaultdict(int)
        for status, cnt in list(job_rows) + list(image_rows):
            counts[str(status or "unknown")] += int(cnt or 0)
        total = sum(counts.values())
        return {
            "total_jobs": total,
            "by_status": dict(counts),
            "completed": counts.get("completed", 0) + counts.get("complete", 0),
            "failed": counts.get("failed", 0),
            "running": counts.get("running", 0)
            + counts.get("pending", 0)
            + counts.get("queued", 0),
            "source": "live_db",
        }

    async def metrics_snapshot(self, org_id: uuid.UUID) -> dict[str, Any]:
        cost = await self.cost(org_id)
        usage = await self.usage(org_id)
        wf = await self.workflow_health(org_id)
        return {
            "counters": {
                "llm_calls": next(
                    (s["value"] for s in usage["signals"] if s["name"] == "llm_calls"), 0
                ),
                "images_completed": next(
                    (s["value"] for s in usage["signals"] if s["name"] == "images_completed"),
                    0,
                ),
                "drafts": next(
                    (s["value"] for s in usage["signals"] if s["name"] == "drafts"), 0
                ),
                "jobs_total": wf["total_jobs"],
                "cost_usd": cost["total"],
            },
            "histograms": {},
            "source": "live_db",
        }
