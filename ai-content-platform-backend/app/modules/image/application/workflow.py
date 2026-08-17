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
from app.modules.image.application.creative_composer import CreativeComposer
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
        composer: CreativeComposer | None = None,
    ) -> None:
        self._session = session
        self._storage = storage or get_storage_provider()
        self._delivery = delivery or get_delivery_strategy()
        self._engine = engine or VisualIntelligenceFactory.create()
        self._orchestrator = orchestrator or AIOrchestratorFactory.create()
        # Second ("white card") variant only — see _execute_gemini_infographic.
        self._composer = composer or CreativeComposer()
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
        # All variants for a draft use ONE provider (per-request override, else the
        # configured default — normally openai). Multiple variants get their visual
        # variety from cycling template styles (see prompt_builder.py), not from
        # mixing providers — a "gemini" + "openai" pair produced the same prompt
        # rendered inconsistently across two different models, which isn't what we
        # want for a client-facing set of style options.
        def _engine_for(provider_name: str | None):
            if not provider_name:
                return self._engine
            eng = VisualIntelligenceFactory.create(provider_name=provider_name)
            eng._assets = MemoryImageAssetStore(storage=self._storage, require_storage=True)
            return eng

        engine = _engine_for(provider.strip() if provider and provider.strip() else None)
        provider_list = [p.strip() for p in (providers or []) if p and p.strip()] or None

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
            "services_line": brand_row.services_line if brand_row else None,
            "footer_text": brand_row.footer_text if brand_row else None,
            "extra_settings": brand_extra,
        }
        logo_bytes: bytes | None = None
        if brand_row and brand_row.logo_object_key:
            try:
                logo_bytes = self._storage.get_bytes(brand_row.logo_object_key)
            except Exception:  # noqa: BLE001 — missing/corrupt logo asset is non-fatal
                logger.warning(
                    "Logo asset unreadable, generating without reference image org_id=%s key=%s",
                    org_id,
                    brand_row.logo_object_key,
                )
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
            jobs.append(
                await self._execute_one(
                    org_id=org_id,
                    draft_id=draft_id,
                    draft_dict=draft_dict,
                    brand=brand,
                    variant_index=variant,
                    image_count=image_count,
                    engine=engine,
                    logo_bytes=logo_bytes,
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
        logo_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        job = ImageJob(
            organization_id=org_id,
            draft_id=draft_id,
            status="running",
        )
        self._session.add(job)
        await self._session.flush()

        # Second image slot ("white card") only — ported gemini_infographic
        # pipeline. Variant 0 ("blue card", alert_card) falls through to the
        # unchanged code below, exactly as it always has.
        if variant_index == 1:
            return await self._execute_gemini_infographic(
                job=job,
                org_id=org_id,
                draft_id=draft_id,
                draft_dict=draft_dict,
                brand=brand,
                variant_index=variant_index,
                image_count=image_count,
                visual_style="auto",
                include_logo=None,
                logo_position=None,
                logo_size=None,
                logo_bytes=logo_bytes,
                quality="premium",
                image_format="square",
                reference_mode="auto",
                creative_mode="gemini_infographic",
            )

        engine = engine or self._engine

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
                logo_bytes=logo_bytes,
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

    # ── gemini_infographic pipeline — second ("white card") image slot only ──
    # Ported from the client's updated_delivery. Uses its own isolated
    # "gemini_infographic" provider (never the shared "gemini"/"openai"
    # providers variant 0 and the rest of the app use) and writes MediaAsset
    # rows with kind="generated_illustration" (not the source's
    # "linkedin_creative") so both cards keep showing up together in the
    # existing gallery query in app/api/routes/images.py.

    async def _set_job_phase(self, job: ImageJob, phase: str, **extra: Any) -> None:
        meta = dict(job.generation_metadata_json or {})
        meta["phase"] = phase
        meta.update({k: v for k, v in extra.items() if v is not None})
        job.generation_metadata_json = _json_safe(meta)
        await self._session.flush()

    async def _execute_gemini_infographic(
        self,
        *,
        job: ImageJob,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        draft_dict: dict[str, Any],
        brand: dict[str, Any],
        variant_index: int,
        image_count: int,
        visual_style: str,
        include_logo: bool | None,
        logo_position: str | None,
        logo_size: str | None,
        logo_bytes: bytes | None,
        quality: str,
        image_format: str,
        reference_mode: str,
        creative_mode: str,
    ) -> dict[str, Any]:
        """Gemini text-in-image infographic path with critic retry + provider fallback."""
        import time

        from app.core.config import get_settings
        from app.infrastructure.image_generation.factory import get_image_provider
        from app.modules.image.application.gemini_infographic_prompt import (
            build_gemini_infographic_prompt,
        )
        from app.modules.image.application.logo_stamp import (
            default_brand_logo_bytes,
            pick_best_corner,
            stamp_brand_logo,
        )
        from app.modules.image.application.reference_policy import ReferenceImagePolicy
        from app.modules.image.application.visual_critic import VisualCreativeCritic
        from app.modules.image.application.visual_strategy import VisualStrategyEngine
        from app.modules.image.domain.models import ImageGenerationRequest

        started = time.perf_counter()
        settings = get_settings()
        mode = creative_mode or "gemini_infographic"

        await self._set_job_phase(job, "preparing_story")
        strategy = VisualStrategyEngine()
        design_spec = strategy.plan(
            draft_dict,
            brand,
            source_excerpt=str(
                (draft_dict.get("metadata") or {}).get("article_excerpt")
                or (draft_dict.get("metadata") or {}).get("source_excerpt")
                or ""
            ),
            visual_style=visual_style,
            quality=quality,
            image_format=image_format,
            include_logo=include_logo,
            logo_position=logo_position,
            logo_size=logo_size,
            variant_index=variant_index,
            creative_mode=mode,
        )
        quality_design = self._composer.design_quality_check(design_spec)

        await self._set_job_phase(
            job,
            "selecting_layout",
            archetype=design_spec.design_archetype,
            design_spec=design_spec.to_dict(),
        )

        ref_policy = ReferenceImagePolicy()
        mark = logo_bytes or (
            default_brand_logo_bytes() if design_spec.logo.enabled else None
        )
        # Never hand the logo to Gemini as a generation reference — an AI
        # reproduction can drift (placement, cropping, redrawing). Always leave
        # empty space in the prompt (include_logo=False below) and composite the
        # real logo file on afterward instead — see the always-stamp block below.
        refs = ref_policy.resolve(
            mode=reference_mode,
            include_logo=False,
            logo_bytes=None,
            brand=brand,
        )

        critic = VisualCreativeCritic()
        max_retries = critic.max_retries() if critic.enabled_for_mode(mode) else 0
        threshold = critic.threshold()
        critic_enabled = critic.enabled_for_mode(mode)

        # Always this pipeline's own isolated Gemini SDK provider — never
        # settings.IMAGE_PROVIDER, which controls the blue card/rest of the app.
        primary_name = "gemini_infographic"
        fallback_name = str(getattr(settings, "IMAGE_PROVIDER_FALLBACK", "") or "").lower()
        provider_chain = [primary_name]
        if fallback_name and fallback_name not in {"none", primary_name}:
            if fallback_name == "openai":
                provider_chain.append("openai")
            # brand_template handled after provider failures

        recommendations: list[str] = []
        best_bytes: bytes = b""
        best_critic: dict[str, Any] = {}
        best_score = -1.0
        result_provider = primary_name
        result_model = ""
        result_cost = 0.0
        result_latency = 0
        attempt = 0
        positive = ""
        negative = ""
        failure_reason: str | None = None
        used_fallback = False
        primary_provider = primary_name
        fallback_provider: str | None = None

        async def _generate_with_provider(
            provider_name: str,
            positive: str,
            negative: str,
            attempt_idx: int,
        ) -> tuple[bytes, str, str, float, int]:
            provider = get_image_provider(provider_name)
            aspect = str((design_spec.metadata or {}).get("aspect_ratio") or "4:5")
            tier = str((design_spec.metadata or {}).get("quality_tier") or quality or "standard")
            gen = await provider.generate(
                ImageGenerationRequest(
                    prompt=positive,
                    width=design_spec.layout.width or 1080,
                    height=design_spec.layout.height or 1350,
                    style="gemini_infographic",
                    negative_prompt=negative,
                    parameters={
                        "quality_tier": tier,
                        "quality": tier,
                        "aspect_ratio": aspect,
                        "reference_images": refs.provider_references(),
                        "output_format": "png",
                    },
                    metadata={
                        "creative_mode": mode,
                        "archetype": design_spec.design_archetype,
                        "attempt": attempt_idx,
                        "aspect_ratio": aspect,
                        "design_spec": design_spec.to_dict(),
                    },
                )
            )
            return (
                gen.image_bytes,
                gen.provider or provider_name,
                gen.model or "",
                float(gen.cost_estimate or 0.0),
                int(gen.latency_ms or 0),
            )

        image_bytes = b""
        for attempt in range(0, max_retries + 1):
            await self._set_job_phase(
                job,
                "generating",
                attempt=attempt,
                archetype=design_spec.design_archetype,
            )
            positive, negative = build_gemini_infographic_prompt(
                design_spec,
                brand=brand,
                creative_mode=mode,
                critic_recommendations=recommendations or None,
                logo_as_reference=refs.logo_as_reference,
            )
            generated = False
            last_err: Exception | None = None
            for pname in provider_chain:
                try:
                    (
                        image_bytes,
                        result_provider,
                        result_model,
                        result_cost,
                        result_latency,
                    ) = await _generate_with_provider(pname, positive, negative, attempt)
                    if pname != primary_name:
                        used_fallback = True
                        fallback_provider = pname
                        failure_reason = failure_reason or "primary_provider_failed"
                    generated = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    logger.exception(
                        "gemini_infographic_provider_failed job=%s provider=%s attempt=%s: %s",
                        job.id,
                        pname,
                        attempt,
                        exc,
                    )
                    failure_reason = f"{pname}:{exc}"[:500]
                    if pname == primary_name and "openai" in provider_chain:
                        used_fallback = True
                        fallback_provider = "openai"

            if not generated:
                # Fall back to brand template compose path
                logger.error(
                    "gemini_infographic_all_providers_failed job=%s err=%s — brand_template",
                    job.id,
                    last_err,
                )
                await self._set_job_phase(job, "applying_brand", fallback="brand_template")
                return await self._execute_brand_template(
                    job=job,
                    org_id=org_id,
                    draft_id=draft_id,
                    design_spec=design_spec,
                    quality=quality_design,
                    variant_index=variant_index,
                    image_count=image_count,
                    logo_bytes=mark,
                )

            # Persist attempt artifact (never overwrite prior finals)
            attempt_key = f"{org_id}/images/{job.id}/attempt_{attempt}.png"
            written_attempt = persist_png(self._storage, attempt_key, image_bytes)
            self._session.add(
                ImageJobArtifact(
                    job_id=job.id,
                    artifact_type=f"attempt_{attempt}",
                    object_key=attempt_key,
                    width=design_spec.layout.width,
                    height=design_spec.layout.height,
                    metadata_json={
                        "attempt": attempt,
                        "provider": result_provider,
                        "model": result_model,
                        **written_attempt,
                    },
                )
            )
            await self._session.flush()

            critic_payload: dict[str, Any] = {"overall": 90.0, "passed": True, "issues": []}
            if critic_enabled:
                await self._set_job_phase(job, "quality_check", attempt=attempt)
                critique = await critic.critique(image_bytes, design_spec, brand=brand)
                critic_payload = critique.to_dict()
                score = float(critique.overall)
                if score > best_score:
                    best_score = score
                    best_bytes = image_bytes
                    best_critic = critic_payload
                if critique.passed or attempt >= max_retries:
                    recommendations = []
                    break
                recommendations = list(critique.recommendations or critique.issues or [])[
                    :8
                ]
                logger.info(
                    "visual_critic_retry job=%s attempt=%s score=%s threshold=%s",
                    job.id,
                    attempt,
                    score,
                    threshold,
                )
                continue
            best_bytes = image_bytes
            best_score = float(critic_payload.get("overall") or 90.0)
            best_critic = critic_payload
            break

        if not best_bytes:
            best_bytes = image_bytes
        final_bytes = best_bytes

        await self._set_job_phase(job, "applying_brand", attempt=attempt)
        if design_spec.logo.enabled and mark:
            # Always composite the real logo file — never rely on the critic to
            # catch a missing/wrong AI-drawn one, since the prompt never asks
            # Gemini to draw a logo at all (see ref_policy.resolve above). Position
            # is picked from the actual generated image (whichever corner is
            # visually flattest) rather than a fixed config value, and a backing
            # plate carries legibility instead of relying on the prompt having
            # left that exact spot blank.
            scale = float(refs.stamp_policy.get("default_stamp_scale") or 0.11)
            try:
                position = pick_best_corner(final_bytes, scale=scale)
            except Exception as exc:  # noqa: BLE001
                logger.warning("logo_position_pick_failed job=%s: %s", job.id, exc)
                position = str(
                    refs.stamp_policy.get("default_stamp_position")
                    or design_spec.logo.position
                    or "bottom_right"
                )
            try:
                final_bytes = stamp_brand_logo(
                    final_bytes,
                    mark,
                    position=position,
                    scale=scale,
                    backing=True,
                )
                best_critic["logo_stamped"] = True
                best_critic["logo_position"] = position
            except Exception as exc:  # noqa: BLE001
                logger.warning("logo_stamp_correction_failed job=%s: %s", job.id, exc)

        await self._set_job_phase(job, "finalizing")
        latency_ms = int((time.perf_counter() - started) * 1000) or result_latency
        backend = storage_backend_name(self._storage)
        final_key = f"{org_id}/images/{job.id}/final.png"
        written = persist_png(self._storage, final_key, final_bytes)

        overall_score = float(best_critic.get("overall") or best_score or 0.0)
        job.status = "completed"
        job.provider = result_provider
        job.model = result_model
        job.latency_ms = latency_ms
        job.cost_estimate = result_cost
        job.quality_score = overall_score
        job.prompt_enhanced = positive[:2000]
        job.quality_breakdown_json = _json_safe(best_critic)
        job.brief_json = {
            "design_spec": design_spec.to_dict(),
            "archetype": design_spec.design_archetype,
            "creative_mode": mode,
            "pipeline": "gemini_infographic",
        }
        job.generation_metadata_json = _json_safe(
            {
                "phase": "completed",
                "variant_index": variant_index,
                "image_count": image_count,
                "design_spec": design_spec.to_dict(),
                "archetype": design_spec.design_archetype,
                "creative_pipeline": "gemini_infographic",
                "creative_mode": mode,
                "quality": quality_design,
                "quality_tier": quality,
                "format": design_spec.format,
                "attempt": attempt,
                "attempts": attempt + 1,
                "primary_provider": primary_provider,
                "fallback_provider": fallback_provider,
                "used_fallback": used_fallback,
                "failure_reason": failure_reason,
                "provider_label": (
                    "Premium" if str(quality).lower() in {"premium", "pro"} else "Standard"
                ),
                "critic": best_critic,
            }
        )
        job.visual_plan_json = {
            "variant_index": variant_index,
            "design_spec": design_spec.to_dict(),
            "creative_mode": mode,
            "pipeline": "gemini_infographic",
        }
        job.retry_count = attempt

        self._session.add(
            ImageJobArtifact(
                job_id=job.id,
                artifact_type="final",
                object_key=final_key,
                width=design_spec.layout.width,
                height=design_spec.layout.height,
                metadata_json={
                    "variant_index": variant_index,
                    "storage_backend": backend,
                    "archetype": design_spec.design_archetype,
                    "creative_pipeline": "gemini_infographic",
                    "quality_score": overall_score,
                    "attempt": attempt,
                    "design_spec": design_spec.to_dict(),
                    **written,
                },
            )
        )
        media = MediaAsset(
            organization_id=org_id,
            draft_id=draft_id,
            # Matches variant 0's kind so both cards show up together in the
            # existing gallery query (app/api/routes/images.py) — the source
            # pipeline used "linkedin_creative", which that query never selects.
            kind="generated_illustration",
            object_key=final_key,
            sha256="",
            width=design_spec.layout.width,
            height=design_spec.layout.height,
            file_size_bytes=int(written.get("size_bytes") or 0),
            mime_type="image/png",
            exif_stripped=True,
            version=1,
        )
        self._session.add(media)
        await self._session.flush()
        media_id = str(media.id)

        logger.info(
            "image_gemini_infographic_completed job=%s provider=%s score=%s attempts=%s",
            job.id,
            result_provider,
            overall_score,
            attempt + 1,
        )

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
                    storage_key=final_key,
                    correlation_id=corr,
                )
            )
        finally:
            reset_event_session(token)

        delivery = self._delivery.resolve(final_key, content_type="image/png")
        return {
            "job_id": str(job.id),
            "status": "completed",
            "variant_index": variant_index,
            "archetype": design_spec.design_archetype,
            "object_key": final_key,
            "storage_key": final_key,
            "storage_backend": backend,
            "media_id": media_id,
            "provider": result_provider,
            "provider_label": (
                "Premium" if str(quality).lower() in {"premium", "pro"} else "Standard"
            ),
            "model": result_model,
            "latency_ms": latency_ms,
            "cost_estimate": result_cost,
            "quality_score": overall_score,
            "phase": "completed",
            "attempt": attempt,
            "url": delivery.url if delivery else None,
            "delivery_strategy": delivery.strategy if delivery else None,
            "correlation_id": corr,
            "design_spec": design_spec.to_dict(),
            "format": design_spec.format,
        }

    async def _execute_brand_template(
        self,
        *,
        job: ImageJob,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        design_spec: Any,
        quality: dict[str, Any],
        variant_index: int,
        image_count: int,
        logo_bytes: bytes | None,
    ) -> dict[str, Any]:
        """Deterministic PIL-composed fallback — used only if Gemini generation
        (including provider fallback) fails outright for the white card."""
        import time

        started = time.perf_counter()
        use_logo = logo_bytes
        if design_spec.logo.enabled and not use_logo:
            from app.modules.image.application.logo_stamp import default_brand_logo_bytes

            use_logo = default_brand_logo_bytes()
        blank = b""
        try:
            final_blob = self._composer.compose(blank, design_spec, logo_bytes=use_logo)
        except Exception as exc:
            logger.exception("brand_template_compose_failed job=%s: %s", job.id, exc)
            job.status = "failed"
            job.error_message = f"brand_template_failed:{exc}"[:1000]
            await self._session.flush()
            return {
                "job_id": str(job.id),
                "status": "failed",
                "error": job.error_message,
                "variant_index": variant_index,
                "archetype": design_spec.design_archetype,
            }

        latency_ms = int((time.perf_counter() - started) * 1000)
        backend = storage_backend_name(self._storage)
        final_key = f"{org_id}/images/{job.id}/final.png"
        written = persist_png(self._storage, final_key, final_blob)

        job.status = "completed"
        job.provider = "brand_template"
        job.model = "guard_iq_editorial_v1"
        job.latency_ms = latency_ms
        job.cost_estimate = 0.0
        job.quality_score = float(quality.get("overall") or 9.0)
        job.prompt_enhanced = f"brand_template:{design_spec.design_archetype}"[:2000]
        job.brief_json = {
            "design_spec": design_spec.to_dict(),
            "archetype": design_spec.design_archetype,
            "creative_mode": "brand_template",
        }
        job.generation_metadata_json = {
            "variant_index": variant_index,
            "image_count": image_count,
            "design_spec": design_spec.to_dict(),
            "archetype": design_spec.design_archetype,
            "creative_pipeline": "brand_template",
            "quality": quality,
        }
        job.visual_plan_json = {
            "variant_index": variant_index,
            "design_spec": design_spec.to_dict(),
            "creative_mode": "brand_template",
        }
        self._session.add(
            ImageJobArtifact(
                job_id=job.id,
                artifact_type="final",
                object_key=final_key,
                width=design_spec.layout.width,
                height=design_spec.layout.height,
                metadata_json={
                    "variant_index": variant_index,
                    "storage_backend": backend,
                    "archetype": design_spec.design_archetype,
                    "creative_pipeline": "brand_template",
                    "design_spec": design_spec.to_dict(),
                    **written,
                },
            )
        )
        media = MediaAsset(
            organization_id=org_id,
            draft_id=draft_id,
            kind="generated_illustration",
            object_key=final_key,
            sha256="",
            width=design_spec.layout.width,
            height=design_spec.layout.height,
            file_size_bytes=int(written.get("size_bytes") or 0),
            mime_type="image/png",
            exif_stripped=True,
            version=1,
        )
        self._session.add(media)
        await self._session.flush()
        media_id = str(media.id)
        logger.info(
            "image_gallery_persisted backend=%s object_key=%s media_id=%s mode=brand_template",
            backend,
            final_key,
            media_id,
        )

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
                    storage_key=final_key,
                    correlation_id=corr,
                )
            )
        finally:
            reset_event_session(token)

        delivery = self._delivery.resolve(final_key, content_type="image/png")
        return {
            "job_id": str(job.id),
            "status": "completed",
            "variant_index": variant_index,
            "archetype": design_spec.design_archetype,
            "object_key": final_key,
            "storage_key": final_key,
            "storage_backend": backend,
            "media_id": media_id,
            "provider": "brand_template",
            "model": "guard_iq_editorial_v1",
            "latency_ms": latency_ms,
            "cost_estimate": 0.0,
            "quality_score": job.quality_score,
            "url": delivery.url if delivery else None,
            "delivery_strategy": delivery.strategy if delivery else None,
            "correlation_id": corr,
            "design_spec": design_spec.to_dict(),
        }
