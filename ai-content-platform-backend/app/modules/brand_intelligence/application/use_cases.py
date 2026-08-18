"""Brand Intelligence application use cases."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.jobs import Job, JobEvent
from app.modules.brand_intelligence.domain.events import (
    brand_import_completed,
    brand_import_started,
    brand_memory_built,
)
from app.modules.brand_intelligence.domain.models import (
    BrandImport,
    BrandImportJob,
    BrandMemory,
    BrandMemoryVersion,
    BrandPersona,
    BrandProfile,
    ImportStatus,
    MemoryLifecycle,
    NeverSayPolicy,
    PersonaKind,
    ProfileKind,
)
from app.modules.brand_intelligence.infrastructure.postgres.repositories import (
    PgBrandImportJobRepository,
    PgBrandImportRepository,
    PgBrandMemoryRepository,
    PgBrandPersonaRepository,
    PgBrandProfileRepository,
    PgBrandReviewRepository,
    PgBrandVectorChunkRepository,
    PgBrowserSessionStore,
    PgCanonicalObjectRepository,
    PgLogoAssetRepository,
    PgNeverSayRepository,
)
from app.modules.organization.infrastructure.brand_kit_repository import PgBrandKitRepository
from app.shared.result import Result, fail, ok


def _correlation(default: str = "") -> str:
    return default or str(uuid.uuid4())


class BrandIntelligenceUseCases:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.profiles = PgBrandProfileRepository(session)
        self.personas = PgBrandPersonaRepository(session)
        self.never_say = PgNeverSayRepository(session)
        self.imports = PgBrandImportRepository(session)
        self.import_jobs = PgBrandImportJobRepository(session)
        self.memories = PgBrandMemoryRepository(session)
        self.reviews = PgBrandReviewRepository(session)
        self.logos = PgLogoAssetRepository(session)
        self.sessions = PgBrowserSessionStore(session)
        self.vectors = PgBrandVectorChunkRepository(session)
        self.cbos = PgCanonicalObjectRepository(session)
        self.brand_kits = PgBrandKitRepository(session)

    async def list_profiles(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        await self.profiles.ensure_default_corporate(org_id)
        await self._session.commit()
        rows = await self.profiles.list_for_org(org_id)
        return [self._profile_dict(p) for p in rows]

    async def create_profile(
        self, org_id: uuid.UUID, *, kind: str, name: str, is_default: bool = False
    ) -> dict[str, Any]:
        if is_default:
            for p in await self.profiles.list_for_org(org_id):
                if p.is_default:
                    p.is_default = False
                    await self.profiles.update(p)
        profile = await self.profiles.create(
            BrandProfile(
                id=uuid.uuid4(),
                organization_id=org_id,
                kind=ProfileKind(kind),
                name=name,
                is_default=is_default,
            )
        )
        await self.personas.upsert(
            BrandPersona(
                id=uuid.uuid4(),
                organization_id=org_id,
                brand_profile_id=profile.id,
                kind=PersonaKind.CEO,
                name="CEO",
                is_default=True,
            )
        )
        await self.never_say.upsert(
            NeverSayPolicy(
                id=uuid.uuid4(),
                organization_id=org_id,
                brand_profile_id=profile.id,
            )
        )
        await self._session.commit()
        return self._profile_dict(profile)

    async def create_import(
        self,
        org_id: uuid.UUID,
        *,
        profile_id: uuid.UUID,
        source_mix: dict[str, Any],
    ) -> Result[dict[str, Any]]:
        profile = await self.profiles.get(org_id, profile_id)
        if not profile:
            return fail("profile_not_found", "Brand profile not found")
        row = await self.imports.create(
            BrandImport(
                id=uuid.uuid4(),
                organization_id=org_id,
                brand_profile_id=profile_id,
                status=ImportStatus.PENDING,
                source_mix_json=source_mix,
            )
        )
        await self._session.commit()
        return ok({"id": str(row.id), "status": row.status.value, "brand_profile_id": str(profile_id)})

    async def import_from_linkedin_url(
        self,
        org_id: uuid.UUID,
        *,
        linkedin_url: str,
        brand_profile_id: uuid.UUID | None = None,
        profile_name: str | None = None,
        max_posts: int = 40,
        website_url: str | None = None,
        correlation_id: str = "",
    ) -> Result[dict[str, Any]]:
        """URL-only product path: ensure profile → import → analyze (live LinkedIn fetch)."""
        url = (linkedin_url or "").strip()
        if "linkedin.com/" not in url.lower():
            return fail("invalid_linkedin_url", "Provide a linkedin.com profile or company URL")

        session_rec = await self.sessions.load(org_id, "linkedin")
        if not session_rec:
            return fail(
                "linkedin_session_required",
                "Connect LinkedIn once (Playwright session) so we can fetch profile, posts, "
                "images, and engagement from the URL. Use POST /brand-intelligence/session/linkedin/start "
                "then save storage_state.",
            )

        if brand_profile_id:
            profile = await self.profiles.get(org_id, brand_profile_id)
            if not profile:
                return fail("profile_not_found", "Brand profile not found")
        else:
            await self.profiles.ensure_default_corporate(org_id)
            profile = await self.profiles.get_default(org_id)
            if not profile:
                created = await self.create_profile(
                    org_id,
                    kind="corporate",
                    name=profile_name or "LinkedIn Brand",
                    is_default=True,
                )
                profile = await self.profiles.get(org_id, uuid.UUID(created["id"]))
            elif profile_name:
                profile.name = profile_name
                await self.profiles.update(profile)
            assert profile is not None

        source_mix: dict[str, Any] = {
            "linkedin_url": url,
            "use_playwright": True,
            "max_posts": max_posts,
            "sources": ["linkedin"],
            "website_url": website_url,
            "artifacts": [],
        }
        if website_url:
            source_mix["sources"] = ["linkedin", "website"]

        created = await self.create_import(org_id, profile_id=profile.id, source_mix=source_mix)
        if created.is_failure:
            return created
        import_id = uuid.UUID(created.value["id"])
        analyzed = await self.start_analyze(org_id, import_id, correlation_id=correlation_id)
        if analyzed.is_failure:
            return analyzed
        return ok(
            {
                "brand_profile_id": str(profile.id),
                "import_id": str(import_id),
                **analyzed.value,
                "linkedin_url": url,
                "mode": "url_fetch",
            }
        )

    async def start_analyze(
        self,
        org_id: uuid.UUID,
        import_id: uuid.UUID,
        *,
        correlation_id: str = "",
    ) -> Result[dict[str, Any]]:
        imp = await self.imports.get(org_id, import_id)
        if not imp:
            return fail("import_not_found", "Import not found")
        corr = _correlation(correlation_id)
        job = Job(
            organization_id=org_id,
            job_type="brand_import",
            status="pending",
            payload_json={"import_id": str(import_id)},
            correlation_id=corr,
        )
        self._session.add(job)
        await self._session.flush()
        self._session.add(
            JobEvent(job_id=job.id, event_type="created", message="brand_import queued")
        )
        bi_job = await self.import_jobs.create(
            BrandImportJob(
                id=uuid.uuid4(),
                organization_id=org_id,
                import_id=import_id,
                job_id=job.id,
                stage="queued",
                progress_pct=0,
                message="Queued",
            )
        )
        await self._session.commit()

        try:
            from app.infrastructure.events.factory import get_event_bus

            await get_event_bus().publish(
                brand_import_started(
                    organization_id=org_id,
                    correlation_id=corr,
                    import_id=import_id,
                    profile_id=imp.brand_profile_id,
                )
            )
        except Exception:
            pass

        backend = os.getenv("JOB_BACKEND", "inline").lower()
        if backend == "dramatiq":
            from app.workers.brand_intelligence import run_brand_import_task

            run_brand_import_task.send(str(org_id), str(import_id), str(job.id), str(bi_job.id))
        else:
            asyncio.create_task(
                self._inline_run(org_id, import_id, job.id, bi_job.id, corr)
            )

        return ok({"job_id": str(job.id), "brand_import_job_id": str(bi_job.id), "status": "accepted"})

    async def _inline_run(
        self,
        org_id: uuid.UUID,
        import_id: uuid.UUID,
        job_id: uuid.UUID,
        bi_job_id: uuid.UUID,
        correlation_id: str,
    ) -> None:
        from app.infrastructure.postgres.session import async_session_factory
        from app.modules.brand_intelligence.application.pipeline import BrandIntelligencePipeline

        async with async_session_factory() as session:
            uc = BrandIntelligenceUseCases(session)
            bi_job = await uc.import_jobs.get(org_id, bi_job_id)
            job = await session.get(Job, job_id)
            if not bi_job or not job:
                return
            job.status = "running"
            await session.commit()
            try:
                session_rec = await uc.sessions.load(org_id, "linkedin")
                pipeline = BrandIntelligencePipeline(
                    session,
                    browser_session_bytes=session_rec.ciphertext if session_rec else None,
                )
                memory = await pipeline.run(org_id=org_id, import_id=import_id, bi_job=bi_job)
                job.status = "completed"
                session.add(JobEvent(job_id=job.id, event_type="completed", message="brand_import done"))
                await session.commit()
                try:
                    from app.infrastructure.events.factory import get_event_bus

                    await get_event_bus().publish(
                        brand_import_completed(
                            organization_id=org_id,
                            correlation_id=correlation_id,
                            import_id=import_id,
                            stage="awaiting_validation",
                            success=True,
                            extra={"memory_id": str(memory.id)},
                        )
                    )
                except Exception:
                    pass
            except Exception as exc:  # noqa: BLE001
                job.status = "failed"
                bi_job.stage = "failed"
                bi_job.message = str(exc)[:500]
                bi_job.error_json = {"error": str(exc)[:500]}
                await uc.import_jobs.update(bi_job)
                session.add(JobEvent(job_id=job.id, event_type="failed", message=str(exc)[:500]))
                await session.commit()

    async def get_job_progress(self, org_id: uuid.UUID, job_id: uuid.UUID) -> Result[dict[str, Any]]:
        bi = await self.import_jobs.get_by_job_id(org_id, job_id)
        if not bi:
            return fail("job_not_found", "Brand import job not found")
        return ok(
            {
                "job_id": str(job_id),
                "import_id": str(bi.import_id),
                "stage": bi.stage,
                "progress_pct": bi.progress_pct,
                "message": bi.message,
                "error": bi.error_json,
                "eta_seconds": bi.eta_seconds,
            }
        )

    async def get_memory(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> Result[dict[str, Any]]:
        mem = await self.memories.get_active(org_id, profile_id)
        if not mem:
            return fail("memory_not_found", "No brand memory for profile")
        return ok(self._memory_dict(mem))

    async def get_review(self, org_id: uuid.UUID, memory_id: uuid.UUID) -> Result[dict[str, Any]]:
        review = await self.reviews.get_open(org_id, memory_id)
        if not review:
            return fail("review_not_found", "No open review")
        return ok(
            {
                "id": str(review.id),
                "memory_id": str(review.memory_id),
                "status": review.status,
                "detections": review.detections_json,
                "edits": review.edits_json,
            }
        )

    async def patch_review(
        self, org_id: uuid.UUID, review_id: uuid.UUID, edits: dict[str, Any]
    ) -> Result[dict[str, Any]]:
        from sqlalchemy import select

        from app.infrastructure.postgres.models.brand_intelligence import BrandMemoryReviewRow
        from app.modules.brand_intelligence.domain.models import BrandMemoryReview

        result = await self._session.execute(
            select(BrandMemoryReviewRow).where(
                BrandMemoryReviewRow.organization_id == org_id,
                BrandMemoryReviewRow.id == review_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return fail("review_not_found", "Review not found")
        review = await self.reviews.save(
            BrandMemoryReview(
                id=row.id,
                organization_id=row.organization_id,
                memory_id=row.memory_id,
                status=row.status,
                detections_json=dict(row.detections_json or {}),
                edits_json=edits,
            )
        )
        await self._session.commit()
        return ok({"id": str(review.id), "edits": review.edits_json})

    async def approve_review(
        self,
        org_id: uuid.UUID,
        review_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
        correlation_id: str = "",
    ) -> Result[dict[str, Any]]:
        from sqlalchemy import select
        from app.infrastructure.postgres.models.brand_intelligence import BrandMemoryReviewRow
        from app.modules.brand_intelligence.domain.models import BrandMemoryReview

        result = await self._session.execute(
            select(BrandMemoryReviewRow).where(
                BrandMemoryReviewRow.organization_id == org_id,
                BrandMemoryReviewRow.id == review_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row or row.status != "open":
            return fail("review_not_found", "Open review not found")

        memory = await self.memories.get(org_id, row.memory_id)
        if not memory:
            return fail("memory_not_found", "Memory not found")

        edits = dict(row.edits_json or {})
        detected = {**(memory.brand_dna_json.get("detected") or {}), **edits}
        memory.brand_dna_json["detected"] = detected
        if "tone" in edits:
            memory.writing_dna_json["tone"] = edits["tone"]
        if "topics" in edits:
            memory.brand_dna_json["topics"] = edits["topics"]

        memory.version_no = memory.version_no + 1
        memory.lifecycle = MemoryLifecycle.FINALIZED
        memory = await self.memories.save(memory)

        snapshot = self._memory_dict(memory)
        await self.memories.save_version(
            BrandMemoryVersion(
                id=uuid.uuid4(),
                organization_id=org_id,
                memory_id=memory.id,
                version_no=memory.version_no,
                snapshot_json=snapshot,
                created_by=user_id,
            )
        )

        # vector chunks
        chunks = self._chunk_memory(memory)
        await self.vectors.replace_for_memory(
            org_id=org_id,
            profile_id=memory.brand_profile_id,
            memory_id=memory.id,
            version_no=memory.version_no,
            chunks=chunks,
        )

        # project brand kit
        await self._project_brand_kit(org_id, memory)

        # Project full relevance profile + sync news connector queries from Brand DNA
        news_sync: dict[str, Any] = {}
        try:
            from app.modules.brand_intelligence.application.news_policy_service import (
                BrandNewsPolicyService,
            )

            news_sync = await BrandNewsPolicyService(self._session).sync_news_sources(
                org_id, profile_id=memory.brand_profile_id
            )
        except Exception:
            news_sync = {}

        profile = await self.profiles.get(org_id, memory.brand_profile_id)
        if profile:
            profile.active_memory_id = memory.id
            await self.profiles.update(profile)

        row.status = "approved"
        await self.reviews.save(
            BrandMemoryReview(
                id=row.id,
                organization_id=row.organization_id,
                memory_id=row.memory_id,
                status="approved",
                detections_json=dict(row.detections_json or {}),
                edits_json=dict(row.edits_json or {}),
            )
        )
        await self._session.commit()

        try:
            from app.infrastructure.events.factory import get_event_bus

            await get_event_bus().publish(
                brand_memory_built(
                    organization_id=org_id,
                    correlation_id=_correlation(correlation_id),
                    memory_id=memory.id,
                    profile_id=memory.brand_profile_id,
                    version_no=memory.version_no,
                    confidence=memory.confidence,
                )
            )
        except Exception:
            pass

        payload = self._memory_dict(memory)
        if news_sync:
            payload["news_policy_sync"] = {
                "sources_updated": news_sync.get("sources_updated"),
                "primary_query": (news_sync.get("policy") or {}).get("primary_query"),
            }
        return ok(payload)

    async def reject_review(self, org_id: uuid.UUID, review_id: uuid.UUID) -> Result[dict[str, Any]]:
        from sqlalchemy import select
        from app.infrastructure.postgres.models.brand_intelligence import BrandMemoryReviewRow
        from app.modules.brand_intelligence.domain.models import BrandMemoryReview

        result = await self._session.execute(
            select(BrandMemoryReviewRow).where(
                BrandMemoryReviewRow.organization_id == org_id,
                BrandMemoryReviewRow.id == review_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return fail("review_not_found", "Review not found")
        memory = await self.memories.get(org_id, row.memory_id)
        if memory:
            memory.lifecycle = MemoryLifecycle.REJECTED
            await self.memories.save(memory)
        await self.reviews.save(
            BrandMemoryReview(
                id=row.id,
                organization_id=row.organization_id,
                memory_id=row.memory_id,
                status="rejected",
                detections_json=dict(row.detections_json or {}),
                edits_json=dict(row.edits_json or {}),
            )
        )
        await self._session.commit()
        return ok({"status": "rejected"})

    async def version_diff(
        self, org_id: uuid.UUID, memory_id: uuid.UUID, v1: int, v2: int
    ) -> Result[dict[str, Any]]:
        a = await self.memories.get_version(org_id, memory_id, v1)
        b = await self.memories.get_version(org_id, memory_id, v2)
        if not a or not b:
            return fail("version_not_found", "One or both versions missing")
        sa, sb = a.snapshot_json, b.snapshot_json
        vocab_a = set(
            ((sa.get("brand_dna") or {}).get("vocabulary") or {}).get("preferred")
            or (sa.get("writing_dna") or {}).get("preferred")
            or []
        )
        vocab_b = set(
            ((sb.get("brand_dna") or {}).get("vocabulary") or {}).get("preferred")
            or (sb.get("writing_dna") or {}).get("preferred")
            or []
        )
        # Prefer detected vocab lists
        if (sa.get("brand_dna") or {}).get("detected", {}).get("vocabulary"):
            vocab_a = set((sa.get("brand_dna") or {})["detected"]["vocabulary"])
        if (sb.get("brand_dna") or {}).get("detected", {}).get("vocabulary"):
            vocab_b = set((sb.get("brand_dna") or {})["detected"]["vocabulary"])
        return ok(
            {
                "from": v1,
                "to": v2,
                "added_vocabulary": sorted(vocab_b - vocab_a),
                "removed_vocabulary": sorted(vocab_a - vocab_b),
                "tone_from": (sa.get("writing_dna") or {}).get("tone"),
                "tone_to": (sb.get("writing_dna") or {}).get("tone"),
                "topics_from": (sa.get("brand_dna") or {}).get("topics"),
                "topics_to": (sb.get("brand_dna") or {}).get("topics"),
                "completeness_from": sa.get("completeness"),
                "completeness_to": sb.get("completeness"),
            }
        )

    async def dashboard(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> Result[dict[str, Any]]:
        mem = await self.memories.get_active(org_id, profile_id)
        if not mem:
            return fail("memory_not_found", "No brand memory")
        return ok(
            {
                "overall_score": (mem.completeness_json or {}).get("overall_brand_score"),
                "health": mem.health_json,
                "confidence": mem.confidence,
                "topics": (mem.brand_dna_json or {}).get("topics"),
                "audience": (mem.writing_dna_json or {}).get("reading_level"),
                "writing_dna": mem.writing_dna_json,
                "visual_dna": mem.visual_dna_json,
                "engagement": mem.engagement_json,
                "missing_assets": (mem.health_json or {}).get("missing_assets"),
                "recommendations": mem.recommendations_json,
                "lifecycle": mem.lifecycle.value,
                "version_no": mem.version_no,
            }
        )

    async def profile_hub(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> Result[dict[str, Any]]:
        """Scraped sources + memory summary for Brand page."""
        profile = await self.profiles.get(org_id, profile_id)
        if not profile:
            return fail("profile_not_found", "Brand profile not found")
        mem = await self.memories.get_active(org_id, profile_id)
        logo = await self.logos.get(org_id, profile_id)
        never = await self.never_say.get(org_id, profile_id)
        sources = await self.cbos.list_for_profile(org_id, profile_id, limit=40)
        from app.modules.brand_intelligence.application.logo_placement import (
            resolve_logo_placement_defaults,
        )

        logo_placement = resolve_logo_placement_defaults(
            mem.visual_dna_json if mem else None,
            has_logo_asset=bool(logo and (logo.primary_key or logo.variants_json)),
        )
        return ok(
            {
                "profile": self._profile_dict(profile),
                "memory": self._memory_dict(mem) if mem else None,
                "logo": {
                    "primary_key": logo.primary_key if logo else None,
                    "variants": (logo.variants_json if logo else {}),
                },
                "logo_placement": logo_placement,
                "never_say": {
                    "forbidden": never.forbidden if never else [],
                    "never_use": never.never_use if never else [],
                    "discouraged": never.discouraged if never else [],
                }
                if never
                else None,
                "sources": [
                    {
                        "id": str(o.id),
                        "object_type": o.object_type.value,
                        "source_type": o.source_type.value,
                        "title": o.title,
                        "body_preview": (o.body_text or "")[:400],
                        "canonical_url": o.canonical_url,
                        "engagement": o.engagement,
                    }
                    for o in sources
                ],
            }
        )

    async def upsert_never_say(
        self, org_id: uuid.UUID, profile_id: uuid.UUID, payload: dict[str, Any]
    ) -> Result[dict[str, Any]]:
        existing = await self.never_say.get(org_id, profile_id)
        policy = existing or NeverSayPolicy(
            id=uuid.uuid4(), organization_id=org_id, brand_profile_id=profile_id
        )
        for key in (
            "forbidden",
            "discouraged",
            "legal_restrictions",
            "compliance_restrictions",
            "avoid_vocabulary",
            "never_use",
        ):
            if key in payload and isinstance(payload[key], list):
                setattr(policy, key, payload[key])
        if "preferred_alternatives" in payload and isinstance(payload["preferred_alternatives"], dict):
            policy.preferred_alternatives = payload["preferred_alternatives"]
        await self.never_say.upsert(policy)
        await self._session.commit()
        return ok(
            {
                "id": str(policy.id),
                "brand_profile_id": str(policy.brand_profile_id),
                "forbidden": policy.forbidden,
                "discouraged": policy.discouraged,
                "legal_restrictions": policy.legal_restrictions,
                "compliance_restrictions": policy.compliance_restrictions,
                "avoid_vocabulary": policy.avoid_vocabulary,
                "never_use": policy.never_use,
                "preferred_alternatives": policy.preferred_alternatives,
            }
        )

    async def _project_brand_kit(self, org_id: uuid.UUID, memory: BrandMemory) -> None:
        logo = await self.logos.get(org_id, memory.brand_profile_id)
        fields: dict[str, Any] = {}
        if logo and logo.primary_key:
            fields["logo_object_key"] = logo.primary_key
        dna = memory.brand_dna_json or {}
        writing = memory.writing_dna_json or {}
        visual = memory.visual_dna_json or {}
        tone = writing.get("tone")
        company = dna.get("company") or dna.get("founder")
        if company:
            fields["name"] = str(company) if dna.get("company") else fields.get("name")
            if dna.get("company"):
                fields["name"] = str(dna["company"])
        if dna.get("headline"):
            fields["services_line"] = str(dna["headline"])[:240]
        colors = visual.get("colors") or (dna.get("visual_hints") or {}).get("colors") or []
        hints = dna.get("visual_hints") or {}
        if hints.get("primary_color"):
            fields["primary_color"] = str(hints["primary_color"])
        elif colors:
            fields["primary_color"] = str(colors[0])
        if hints.get("secondary_color"):
            fields["secondary_color"] = str(hints["secondary_color"])
        elif len(colors) > 1:
            fields["secondary_color"] = str(colors[1])
        if hints.get("accent_color"):
            fields["accent_color"] = str(hints["accent_color"])
        if tone:
            fields["tone_json"] = {
                "tone": tone,
                "voice": tone,
                "audience": dna.get("audience") or writing.get("reading_level"),
                "industry": (dna.get("industries") or [None])[0],
                "from_brand_intelligence": True,
                "linkedin_url": dna.get("linkedin_url"),
                "founder": dna.get("founder"),
            }
        detected = dna.get("detected") or {}
        topics = dna.get("topics") or []
        topic_labels = [
            t.get("label", "") if isinstance(t, dict) else str(t) for t in topics[:10]
        ]
        profile_bits = [
            f"# {dna.get('company') or 'Brand'} — Brand Memory",
            f"**Founder / face:** {dna.get('founder') or '—'}",
            f"**LinkedIn:** {dna.get('linkedin_url') or '—'}",
            f"**Headline:** {dna.get('headline') or '—'}",
            f"**Mission:** {dna.get('mission') or detected.get('mission') or '—'}",
            f"**Tone:** {detected.get('tone') or tone or 'professional'}",
            f"**Audience:** {dna.get('audience') or writing.get('reading_level') or '—'}",
            f"**Industries:** {', '.join(str(x) for x in (dna.get('industries') or []))}",
            f"**Topics:** {', '.join(topic_labels)}",
            "",
            "## Scraped writing sample topics",
            ", ".join(topic_labels) or "—",
        ]
        fields["client_profile_md"] = "\n\n".join(profile_bits)
        if fields:
            kit = await self.brand_kits.get_by_org_id(org_id)
            if kit:
                await self.brand_kits.update(kit.id, fields)

    def _chunk_memory(self, memory: BrandMemory) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        sections = {
            "brand_dna": str(memory.brand_dna_json),
            "writing_dna": str(memory.writing_dna_json),
            "visual_dna": str(memory.visual_dna_json),
            "topics": str(memory.brand_dna_json.get("topics")),
            "vocabulary": str((memory.brand_dna_json.get("detected") or {}).get("vocabulary")),
            "hooks": str(memory.brand_dna_json.get("hooks")),
            "ctas": str(memory.brand_dna_json.get("ctas")),
        }
        for section, text in sections.items():
            if text and text not in ("None", "[]", "{}"):
                chunks.append({"section": section, "text": text[:4000], "metadata_json": {}})
        return chunks

    @staticmethod
    def _profile_dict(p: BrandProfile) -> dict[str, Any]:
        return {
            "id": str(p.id),
            "organization_id": str(p.organization_id),
            "kind": p.kind.value,
            "name": p.name,
            "is_default": p.is_default,
            "active_memory_id": str(p.active_memory_id) if p.active_memory_id else None,
        }

    @staticmethod
    def _memory_dict(m: BrandMemory) -> dict[str, Any]:
        return {
            "id": str(m.id),
            "brand_profile_id": str(m.brand_profile_id),
            "version_no": m.version_no,
            "lifecycle": m.lifecycle.value,
            "confidence": m.confidence,
            "brand_dna": m.brand_dna_json,
            "writing_dna": m.writing_dna_json,
            "visual_dna": m.visual_dna_json,
            "engagement": m.engagement_json,
            "completeness": m.completeness_json,
            "health": m.health_json,
            "recommendations": m.recommendations_json,
        }
