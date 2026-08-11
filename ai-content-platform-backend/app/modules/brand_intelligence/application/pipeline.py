"""Brand Intelligence analysis pipeline."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any, Callable, Awaitable

from app.modules.brand_intelligence.application.engines.core import (
    DefaultCompletenessEngine,
    DefaultHealthEngine,
    DefaultRecommendationEngine,
    DefaultSemanticMergeEngine,
    HeuristicCtaAnalyzer,
    HeuristicEngagementAnalyzer,
    HeuristicHookAnalyzer,
    HeuristicOcrProvider,
    HeuristicTopicAnalyzer,
    HeuristicVisionAnalyzer,
    HeuristicVocabularyAnalyzer,
    HeuristicWritingAnalyzer,
)
from app.modules.brand_intelligence.domain.models import (
    BrandImport,
    BrandImportJob,
    BrandMemory,
    BrandMemoryReview,
    CanonicalBrandObject,
    ImportStatus,
    MemoryLifecycle,
)
from app.modules.brand_intelligence.infrastructure.connectors.registry import ConnectorRegistry
from app.modules.brand_intelligence.infrastructure.postgres.repositories import (
    PgBrandImportJobRepository,
    PgBrandImportRepository,
    PgBrandMemoryRepository,
    PgBrandReviewRepository,
    PgCanonicalObjectRepository,
    PgLogoAssetRepository,
)


ProgressCb = Callable[[str, int, str], Awaitable[None]]


class BrandIntelligencePipeline:
    def __init__(self, session: Any, *, browser_session_bytes: bytes | None = None) -> None:
        self._session = session
        self._imports = PgBrandImportRepository(session)
        self._jobs = PgBrandImportJobRepository(session)
        self._cbos = PgCanonicalObjectRepository(session)
        self._memories = PgBrandMemoryRepository(session)
        self._reviews = PgBrandReviewRepository(session)
        self._logos = PgLogoAssetRepository(session)
        self._connectors = ConnectorRegistry()
        self._browser_session_bytes = browser_session_bytes
        self._ocr = HeuristicOcrProvider()
        self._vision = HeuristicVisionAnalyzer()
        self._writing = HeuristicWritingAnalyzer()
        self._topics = HeuristicTopicAnalyzer()
        self._vocab = HeuristicVocabularyAnalyzer()
        self._hooks = HeuristicHookAnalyzer()
        self._ctas = HeuristicCtaAnalyzer()
        self._engagement = HeuristicEngagementAnalyzer()
        self._merge = DefaultSemanticMergeEngine()
        self._completeness = DefaultCompletenessEngine()
        self._health = DefaultHealthEngine()
        self._recs = DefaultRecommendationEngine()

    async def run(
        self,
        *,
        org_id: uuid.UUID,
        import_id: uuid.UUID,
        bi_job: BrandImportJob,
        on_progress: ProgressCb | None = None,
    ) -> BrandMemory:
        async def progress(stage: str, pct: int, message: str) -> None:
            bi_job.stage = stage
            bi_job.progress_pct = pct
            bi_job.message = message
            await self._jobs.update(bi_job)
            await self._session.commit()
            if on_progress:
                await on_progress(stage, pct, message)

        imp = await self._imports.get(org_id, import_id)
        if not imp:
            raise ValueError("import_not_found")

        imp.status = ImportStatus.COLLECTING
        await self._imports.update(imp)
        await progress("collecting", 5, "Collecting brand sources")

        mix = dict(imp.source_mix_json or {})
        all_objects: list[CanonicalBrandObject] = []
        source_types: list[str] = []

        # LinkedIn
        if mix.get("linkedin_url"):
            source_types.append("linkedin")
            conn = self._connectors.get("linkedin")
            cfg = {
                "organization_id": str(org_id),
                "brand_profile_id": str(imp.brand_profile_id),
                "import_id": str(import_id),
                "linkedin_url": mix.get("linkedin_url"),
                "about": mix.get("linkedin_about"),
                "headline": mix.get("linkedin_headline"),
                "display_name": mix.get("linkedin_display_name"),
                "company": mix.get("company") or mix.get("linkedin_company"),
                "location": mix.get("location") or mix.get("linkedin_location"),
                "website": mix.get("website_url") or mix.get("website"),
                "posts": mix.get("linkedin_posts") or [],
                # Live scrape whenever a browser session exists (URL-only product path).
                "use_playwright": bool(mix.get("use_playwright"))
                or bool(self._browser_session_bytes),
                "max_posts": int(mix.get("max_posts") or 40),
            }
            all_objects.extend(await conn.fetch(cfg, self._browser_session_bytes))

        if mix.get("website_url"):
            source_types.append("website")
            await progress("collecting_website", 15, "Crawling website")
            conn = self._connectors.get("website")
            all_objects.extend(
                await conn.fetch(
                    {
                        "organization_id": str(org_id),
                        "brand_profile_id": str(imp.brand_profile_id),
                        "import_id": str(import_id),
                        "website_url": mix.get("website_url"),
                        "max_pages": mix.get("max_pages", 8),
                    }
                )
            )

        artifacts = mix.get("artifacts") or []
        if artifacts:
            source_types.append("upload")
            await progress("collecting_uploads", 25, "Ingesting uploads")
            conn = self._connectors.get("upload")
            all_objects.extend(
                await conn.fetch(
                    {
                        "organization_id": str(org_id),
                        "brand_profile_id": str(imp.brand_profile_id),
                        "import_id": str(import_id),
                        "artifacts": artifacts,
                    }
                )
            )

        await progress("normalize", 35, f"Normalized {len(all_objects)} canonical objects")
        await self._cbos.bulk_upsert(all_objects)
        await self._session.commit()

        await progress("ocr", 45, "OCR analysis")
        ocr_results = []
        for obj in all_objects:
            for ref in obj.media_refs:
                key = ref.get("storage_key")
                if key:
                    ocr_results.append(await self._ocr.extract(str(key)))

        await progress("vision", 55, "Vision analysis")
        vision_results = []
        for obj in all_objects:
            for ref in obj.media_refs:
                key = ref.get("storage_key")
                if key:
                    vision_results.append(await self._vision.analyze(str(key)))

        await progress("nlp", 65, "Writing / topic / vocabulary analysis")
        writing = await self._writing.analyze(all_objects)
        topics = await self._topics.analyze(all_objects)
        vocab = await self._vocab.analyze(all_objects)
        hooks = await self._hooks.analyze(all_objects)
        ctas = await self._ctas.analyze(all_objects)
        engagement = await self._engagement.analyze(all_objects)

        await progress("merge", 75, "Semantic merge into Brand Memory draft")
        analyses = {
            "ocr": ocr_results,
            "vision": vision_results,
            "writing": writing,
            "topics": topics,
            "vocabulary": vocab,
            "hooks": hooks,
            "ctas": ctas,
            "engagement": engagement,
        }
        draft = self._merge.merge(all_objects, analyses, org_id, imp.brand_profile_id)

        logo = await self._logos.get(org_id, imp.brand_profile_id)
        source_mix = {
            "sources": source_types,
            "has_logo": bool(logo and (logo.primary_key or logo.variants_json)),
            "has_guidelines": any(a.get("kind") == "guideline" for a in artifacts if isinstance(a, dict)),
        }
        completeness = self._completeness.score(draft, source_mix)
        health = self._health.evaluate(draft, completeness)
        recs = self._recs.recommend(draft, completeness, health)

        await progress("awaiting_validation", 85, "Awaiting human validation")
        memory = BrandMemory(
            id=uuid.uuid4(),
            organization_id=org_id,
            brand_profile_id=imp.brand_profile_id,
            version_no=0,
            lifecycle=MemoryLifecycle.AWAITING_VALIDATION,
            confidence=draft.confidence,
            brand_dna_json=draft.brand_dna,
            writing_dna_json=draft.writing_dna,
            visual_dna_json=draft.visual_dna,
            engagement_json=draft.engagement_json,
            completeness_json=asdict(completeness),
            health_json=asdict(health),
            recommendations_json=[asdict(r) for r in recs],
        )
        # stash topics/hooks/ctas/vocab into brand_dna for review UI
        memory.brand_dna_json = {
            **memory.brand_dna_json,
            "topics": draft.topics,
            "hooks": draft.hooks,
            "ctas": draft.ctas,
            "vocabulary": draft.vocabulary,
            "detected": draft.detected,
        }
        memory = await self._memories.save(memory)

        review = BrandMemoryReview(
            id=uuid.uuid4(),
            organization_id=org_id,
            memory_id=memory.id,
            status="open",
            detections_json=draft.detected,
            edits_json={},
        )
        await self._reviews.save(review)

        imp.status = ImportStatus.AWAITING_VALIDATION
        await self._imports.update(imp)
        await progress("awaiting_validation", 90, "Review detected brand attributes")
        await self._session.commit()
        return memory
