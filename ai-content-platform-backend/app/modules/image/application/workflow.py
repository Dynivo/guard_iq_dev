"""Visual workflow API facade — delegates to Visual Intelligence Engine (no typography)."""

from __future__ import annotations

import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.infrastructure.postgres.models.branding import BrandKit
from app.infrastructure.postgres.models.carousel import MediaAsset
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.imaging import ImageJob, ImageJobArtifact
from app.infrastructure.storage.factory import get_delivery_strategy, get_storage_provider
from app.modules.assets.domain.ports import DeliveryStrategy, StorageProvider
from app.modules.image.application.assets import (
    MemoryImageAssetStore,
    persist_png,
    storage_backend_name,
)
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.image.application.count_policy import resolve_image_count
from app.modules.image.application.content_subject import inject_content_into_brief
from app.modules.image.application.factory import VisualIntelligenceFactory
from app.modules.image.domain.models import ImagePipelineRequest

logger = get_logger(__name__)


def _json_safe(value: Any) -> Any:
    """Make values JSON/JSONB-safe (reject NaN/Inf floats)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


class VisualWorkflow:
    """Persisting API entrypoint for M10 — illustration assets only (no typography)."""

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageProvider | None = None,
        delivery: DeliveryStrategy | None = None,
        engine=None,
        orchestrator=None,
    ) -> None:
        self._session = session
        self._storage = storage or get_storage_provider()
        self._delivery = delivery or get_delivery_strategy()
        self._engine = engine or VisualIntelligenceFactory.create()
        self._orchestrator = orchestrator or AIOrchestratorFactory.create()
        # Always bind durable storage (local disk via STORAGE_PROVIDER)
        self._engine._assets = MemoryImageAssetStore(
            storage=self._storage, require_storage=True
        )
        logger.info(
            "VisualWorkflow ready storage_backend=%s",
            storage_backend_name(self._storage),
        )

    async def execute(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        *,
        count: int | None = None,
        guidance: str | None = None,
        provider: str | None = None,
        providers: list[str] | None = None,
    ) -> dict[str, Any]:
        provider_list = [p.strip() for p in (providers or []) if p and p.strip()] or None

        def _engine_for(provider_name: str | None):
            if not provider_name:
                return self._engine
            # Per-request provider override (e.g. user picked "gemini", or a
            # multi-provider compare) — build a one-off engine instead of the
            # process default.
            eng = VisualIntelligenceFactory.create(provider_name=provider_name)
            eng._assets = MemoryImageAssetStore(storage=self._storage, require_storage=True)
            return eng

        engine = _engine_for(provider.strip() if provider and provider.strip() else None)

        draft = await self._session.get(Draft, draft_id)
        if draft is None or draft.organization_id != org_id:
            raise NotFoundError("Draft", str(draft_id))

        brand_row = (
            await self._session.execute(
                select(BrandKit).where(BrandKit.organization_id == org_id).limit(1)
            )
        ).scalar_one_or_none()
        brand_extra = dict(brand_row.extra_settings or {}) if brand_row else {}
        image_count = (
            len(provider_list) if provider_list else resolve_image_count(count, brand_extra=brand_extra)
        )
        brand = {
            "name": brand_row.name if brand_row else "Brand",
            "primary_color": brand_row.primary_color if brand_row else "#0A1F2B",
            "secondary_color": (
                brand_row.secondary_color if brand_row and brand_row.secondary_color else "#FFFFFF"
            ),
            "accent_color": (
                brand_row.accent_color if brand_row and brand_row.accent_color else "#1A5CB0"
            ),
            "extra_settings": brand_extra,
        }
        brand_palette = [
            c
            for c in (
                brand.get("primary_color"),
                brand.get("secondary_color"),
                brand.get("accent_color"),
                "#F4F7F5",
            )
            if c
        ]

        visual = await inject_content_into_brief(
            draft.visual_brief_json
            or (draft.metadata_json or {}).get("visual_brief")
            or (draft.metadata_json or {}).get("image_brief"),
            hook=draft.hook or "",
            body=(draft.edited_text or draft.generated_text or "") or "",
            cta=draft.cta or "",
            title=getattr(draft, "title", None) or draft.hook or "",
            article_title=str(
                (draft.metadata_json or {}).get("article_title")
                or (draft.draft_metadata_json or {}).get("article_title")
                or ""
            ),
            content_type=str(draft.content_type or "educational"),
            brand_palette=brand_palette,
            brand=brand,
            linkedin_image_type="single_post",
            orchestrator=self._orchestrator,
            organization_id=str(org_id),
        )
        if guidance and guidance.strip():
            g = guidance.strip()
            visual["scene"] = f"{visual.get('scene') or ''}. Client image guidance: {g}"
            visual["scene_hint"] = visual["scene"]
            meta = dict(visual.get("metadata") or {})
            meta["must_depict"] = f"{meta.get('must_depict') or ''}. Also follow: {g}"
            meta["image_guidance"] = g
            visual["metadata"] = meta

        draft_dict: dict[str, Any] = {
            "id": str(draft.id),
            "hook": draft.hook,
            "body": draft.edited_text or draft.generated_text,
            "cta": draft.cta,
            "content_type": draft.content_type,
            "format": (draft.draft_json or {}).get("format") if draft.draft_json else "single",
            "metadata": dict(draft.metadata_json or {}),
            "visual_brief": visual,
        }

        jobs: list[dict[str, Any]] = []
        for variant in range(image_count):
            variant_engine = (
                _engine_for(provider_list[variant]) if provider_list else engine
            )
            jobs.append(
                await self._execute_one(
                    org_id=org_id,
                    draft_id=draft_id,
                    draft_dict=draft_dict,
                    brand=brand,
                    variant_index=variant,
                    image_count=image_count,
                    engine=variant_engine,
                )
            )

        primary = jobs[0] if jobs else {}
        return {
            **primary,
            "count": len(jobs),
            "jobs": jobs,
            "default_image_count": int(brand_extra.get("default_image_count") or 1),
        }

    async def _execute_one(
        self,
        *,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        draft_dict: dict[str, Any],
        brand: dict[str, Any],
        variant_index: int,
        image_count: int,
        engine=None,
    ) -> dict[str, Any]:
        engine = engine or self._engine
        job = ImageJob(
            organization_id=org_id,
            draft_id=draft_id,
            status="running",
        )
        self._session.add(job)
        await self._session.flush()

        result = await engine.run(
            ImagePipelineRequest(
                organization_id=str(org_id),
                draft_id=str(draft_id),
                draft=draft_dict,
                brand=brand,
                correlation_id="",
                variant_index=variant_index,
                image_count=image_count,
                seed_override=(abs(hash(f"{draft_id}:{variant_index}")) % (2**31))
                if variant_index
                else None,
            )
        )

        job.visual_plan_json = {
            "brief": result.brief.to_dict(),
            "scene": result.scene.to_dict(),
            "composition": result.composition.to_dict(),
            "policy": result.policy.to_dict(),
            "variant_index": variant_index,
        }
        job.prompt_enhanced = result.prompt_request.positive_prompt[:2000]
        job.prompt_hash = result.prompt_hash
        job.workflow_id = result.workflow_id
        job.workflow_version = result.workflow_version
        job.scene_plan_json = result.scene.to_dict()
        job.composition_plan_json = result.composition.to_dict()
        job.policy_json = result.policy.to_dict()
        job.validation_json = result.validation.to_dict()
        job.prompt_request_json = result.prompt_request.to_dict()
        job.generation_metadata_json = {
            **dict(result.metadata),
            "variant_index": variant_index,
            "image_count": image_count,
        }
        job.queue_time_ms = result.queue_time_ms
        job.retry_count = result.retry_count
        job.provider = result.provider
        job.model = result.model
        job.latency_ms = result.latency_ms
        job.cost_estimate = result.cost_estimate
        job.quality_score = result.quality_score
        job.layout_plan_json = result.layout.to_dict() if result.layout else None
        job.asset_intelligence_json = (
            result.asset_intelligence.to_dict() if result.asset_intelligence else None
        )
        job.quality_breakdown_json = result.quality.to_dict() if result.quality else None
        job.embedding_json = (
            _json_safe(
                {k: v for k, v in result.embedding.to_dict().items() if k != "vector"}
                | {
                    "dimensions": result.embedding.dimensions,
                    "vector": list(result.embedding.vector),
                }
            )
            if result.embedding
            else None
        )
        job.seed = result.seed
        job.brief_json = result.brief.to_dict()

        if result.status != "completed":
            job.status = result.status
            job.error_message = ",".join(
                result.validation.reason_codes or result.policy.reason_codes
            )[:1000]
            await self._session.flush()
            return {
                "job_id": str(job.id),
                "status": job.status,
                "error": job.error_message,
                "variant_index": variant_index,
                "provider": job.provider or result.provider or "",
                "model": job.model or result.model or "",
                "validation": result.validation.to_dict(),
                "policy": result.policy.to_dict(),
                "metadata": {
                    "variant_index": variant_index,
                    "image_count": image_count,
                    "reason_codes": list(result.policy.reason_codes or ()),
                },
            }

        primary_key = None
        media_id = None
        # One MediaAsset per generated variant — prefer optimized (not original+optimized,
        # which doubled the gallery count when the user asked for 1 image).
        gallery_asset = None
        for asset in result.assets:
            if asset.role == "optimized":
                gallery_asset = asset
                break
        if gallery_asset is None:
            for asset in result.assets:
                if asset.role == "original":
                    gallery_asset = asset
                    break

        backend = storage_backend_name(self._storage)
        blobs = getattr(engine._assets, "blobs", {}) or {}
        gallery_size = 0

        try:
            for asset in result.assets:
                role = asset.role
                key = f"{org_id}/images/{job.id}/{role}.png"
                blob = blobs.get(asset.object_key) or blobs.get(key)
                if blob is None and asset.object_key and self._storage.exists(asset.object_key):
                    blob = self._storage.get_bytes(asset.object_key)
                if blob is None:
                    raise RuntimeError(
                        f"Missing image bytes for role={role} job={job.id} — "
                        f"cannot persist to {backend}"
                    )
                written = persist_png(self._storage, key, blob)
                artifact = ImageJobArtifact(
                    job_id=job.id,
                    artifact_type=role,
                    object_key=key,
                    width=asset.width,
                    height=asset.height,
                    metadata_json={
                        **dict(asset.metadata),
                        "variant_index": variant_index,
                        "storage_backend": backend,
                        **written,
                    },
                )
                self._session.add(artifact)
                if gallery_asset is not None and asset.role == gallery_asset.role:
                    gallery_size = int(written["size_bytes"])
        except Exception as exc:
            logger.exception(
                "image_persist_failed backend=%s job=%s: %s", backend, job.id, exc
            )
            job.status = "failed"
            job.error_message = f"storage_write_failed:{backend}:{exc}"[:1000]
            await self._session.flush()
            return {
                "job_id": str(job.id),
                "status": job.status,
                "error": job.error_message,
                "variant_index": variant_index,
                "storage_backend": backend,
                "provider": job.provider or result.provider or "",
                "model": job.model or result.model or "",
                "validation": result.validation.to_dict(),
                "policy": result.policy.to_dict(),
                "metadata": {
                    "variant_index": variant_index,
                    "image_count": image_count,
                    "storage_backend": backend,
                },
            }

        if gallery_asset is not None:
            role = gallery_asset.role
            object_key = f"{org_id}/images/{job.id}/{role}.png"
            primary_key = object_key
            media = MediaAsset(
                organization_id=org_id,
                draft_id=draft_id,
                kind="generated_illustration",
                object_key=object_key,
                sha256=gallery_asset.sha256,
                width=gallery_asset.width,
                height=gallery_asset.height,
                file_size_bytes=gallery_size or 0,
                mime_type="image/png",
                exif_stripped=True,
                version=1,
            )
            self._session.add(media)
            await self._session.flush()
            media_id = str(media.id)
            logger.info(
                "image_gallery_persisted backend=%s object_key=%s media_id=%s",
                backend,
                object_key,
                media_id,
            )

        job.status = "completed"
        if result.embedding is not None:
            result.embedding.job_id = str(job.id)
            engine.embedding_service.store.put(result.embedding)  # type: ignore[attr-defined]
            job.embedding_json = _json_safe(result.embedding.to_dict())

        await self._session.flush()

        from app.core.observability import ensure_correlation_id
        from app.infrastructure.events.factory import get_event_bus
        from app.shared.events import image_generated
        from app.shared.events.session_context import reset_event_session, set_event_session

        corr = ensure_correlation_id()
        token = set_event_session(self._session)
        try:
            await get_event_bus().publish(
                image_generated(
                    organization_id=org_id,
                    draft_id=draft_id,
                    job_id=job.id,
                    storage_key=primary_key or "",
                    correlation_id=corr,
                )
            )
        finally:
            reset_event_session(token)

        delivery = (
            self._delivery.resolve(primary_key, content_type="image/png") if primary_key else None
        )
        return {
            "job_id": str(job.id),
            "status": job.status,
            "variant_index": variant_index,
            "object_key": primary_key,
            "storage_key": primary_key,
            "storage_backend": storage_backend_name(self._storage),
            "media_id": media_id,
            "provider": job.provider,
            "model": job.model,
            "latency_ms": job.latency_ms,
            "cost_estimate": job.cost_estimate,
            "quality_score": job.quality_score,
            "url": delivery.url if delivery else None,
            "delivery_strategy": delivery.strategy if delivery else None,
            "correlation_id": corr,
        }
