"""Content use cases: generate draft, list drafts, get draft, update draft."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DraftStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.ai.domain.ports import AIOrchestrator
from app.infrastructure.postgres.models.capture import CaptureSession
from app.infrastructure.postgres.models.content import (
    Draft,
    DraftVariation,
    DraftVersion,
    GenerationReplay,
    PromptHistory,
)
from app.infrastructure.postgres.models.news import Article
from app.modules.content.application.claims_guard import ClaimsGuard
from app.modules.content.application.generation.engine import (
    DefaultContentGenerationEngine,
)
from app.modules.content.application.generation.regenerator import DefaultDraftRegenerator
from app.modules.content.application.generator import ContentGenerator
from app.modules.content.domain.models import RegenSection, StructuredDraft
from app.modules.content.infrastructure.repositories import (
    PgDraftRepository,
    PgDraftVariationRepository,
)

logger = get_logger(__name__)


def _needs_body_enrichment(body: str, summary: str) -> bool:
    text = f"{body}\n{summary}".strip()
    if not text:
        return True
    return "ONLY AVAILABLE IN PAID" in text.upper() or len(text) < 80


async def _fetch_article_plaintext(url: str | None, *, max_chars: int = 4000) -> str:
    """Best-effort public page text for paywalled news APIs."""
    if not url:
        return ""
    try:
        import re

        import httpx

        async with httpx.AsyncClient(
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": "AIContentPlatform/1.0"},
        ) as client:
            response = await client.get(url)
        if response.status_code >= 400:
            return ""
        html = response.text
        # Strip scripts/styles then tags — good enough for grounding LinkedIn drafts.
        html = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        logger.debug("Article URL enrichment failed for %s", url, exc_info=True)
        return ""


class GenerateDraftUseCase:
    """Generate a content draft from an article.

    Pipeline: fetch article → generate content → claims guard → persist draft + variations.
    """

    def __init__(self, session: AsyncSession, orchestrator: AIOrchestrator | None = None) -> None:
        self._session = session
        self._generator = ContentGenerator(session, orchestrator or AIOrchestratorFactory.create())
        self._claims_guard = ClaimsGuard(session)
        self._draft_repo = PgDraftRepository(session)
        self._variation_repo = PgDraftVariationRepository(session)

    async def execute(
        self,
        org_id: uuid.UUID,
        article_id: uuid.UUID,
        content_type: str = "educational",
        force: bool = False,
        *,
        origin: str = "manual_news",
    ) -> dict:
        """Generate a draft from the given article. Returns a dict representing the draft.

        ``origin``:
        - ``manual_news`` — operator one-off from News/Opportunities (excluded from CI plan/calendar)
        - ``content_intelligence_plan`` — AI plan regenerate/fill (counts toward mix + calendar)
        """
        stmt = select(Article).where(Article.id == article_id)
        result = await self._session.execute(stmt)
        article = result.scalar_one_or_none()

        if article is None:
            raise NotFoundError("Article", str(article_id))
        if article.organization_id != org_id:
            raise NotFoundError("Article", str(article_id))

        from app.core.constants import ArticleStatus

        # Warn only for hard low-fit (irrelevant)
        relevance_warning = article.status in (ArticleStatus.IRRELEVANT, "irrelevant")
        _ = force

        title = article.title
        summary = article.summary or ""
        body_text = article.body_text or ""
        # NewsData free plans often store a paywall stub — enrich from the public URL.
        if _needs_body_enrichment(body_text, summary):
            fetched = await _fetch_article_plaintext(article.url)
            if fetched:
                body_text = fetched
                if not summary:
                    summary = fetched[:500]
                article.body_text = body_text
                if not article.summary:
                    article.summary = summary
                await self._session.flush()

        generated = await self._generator.generate(
            org_id=org_id,
            article_id=article_id,
            title=title,
            summary=summary,
            body_text=body_text,
            content_type=content_type,
        )

        source_text = f"{title}\n{summary}\n{body_text}"
        generated_text = generated.get("body", "")
        claims_result = await self._claims_guard.verify(
            org_id=org_id,
            text=generated_text,
            source_text=source_text,
        )

        # Persist only when generation pipeline validated (M9 acceptance)
        if generated.get("validation_passed") is False:
            errors = generated.get("errors") or ["validation failed"]
            logger.warning(
                "Draft generation failed validation; not persisting finalized draft article_id=%s errors=%s",
                article_id,
                errors,
            )
            raise ValidationError(
                f"Draft generation failed validation: {'; '.join(str(e) for e in errors)}"
            )

        draft = Draft(
            article_id=article_id,
            organization_id=org_id,
            content_type=content_type,
            status=DraftStatus.PENDING_REVIEW,
            generated_text=generated_text,
            edited_text=None,
            hook=generated.get("hook", ""),
            cta=generated.get("cta", ""),
            hashtags_json=generated.get("hashtags", []),
            metadata_json={
                "claims_guard": {
                    "passed": claims_result.passed,
                    "flagged": claims_result.flagged_claims,
                },
                "content_type": content_type,
                "validation_passed": True,
                "quality_score": generated.get("quality_score"),
                "confidence_score": generated.get("confidence_score"),
                "replay_id": generated.get("replay_id"),
                "draft": generated.get("draft"),
                "metrics": generated.get("metrics"),
                "quality": (generated.get("draft") or {}).get("quality")
                if isinstance(generated.get("draft"), dict)
                else None,
                "visual_brief": (generated.get("draft") or {}).get("visual_brief")
                if isinstance(generated.get("draft"), dict)
                else None,
                "safety": (generated.get("draft") or {}).get("safety")
                if isinstance(generated.get("draft"), dict)
                else None,
                "draft_metadata": (generated.get("draft") or {}).get("draft_metadata")
                if isinstance(generated.get("draft"), dict)
                else None,
                "source_text": source_text[:2000],
                "relevance_warning": relevance_warning,
                "article_status": article.status,
                "origin": origin,
                "plan_origin": origin == "content_intelligence_plan",
            },
            version=1,
        )
        draft = await self._draft_repo.create(draft)

        variations = generated.get("variations", [])
        if variations:
            variation_models = [
                DraftVariation(
                    draft_id=draft.id,
                    variation_index=i,
                    text=v.get("body", ""),
                    hook=v.get("hook", ""),
                    metadata_json=None,
                )
                for i, v in enumerate(variations)
            ]
            await self._variation_repo.create_batch(variation_models)

        from app.core.observability import ensure_correlation_id
        from app.infrastructure.events.factory import get_event_bus
        from app.shared.events import draft_generated
        from app.shared.events.session_context import reset_event_session, set_event_session

        corr = ensure_correlation_id()
        token = set_event_session(self._session)
        try:
            await get_event_bus().publish(
                draft_generated(
                    organization_id=org_id,
                    draft_id=draft.id,
                    article_id=article_id,
                    correlation_id=corr,
                )
            )
        finally:
            reset_event_session(token)

        logger.info(
            "Draft generated: draft_id=%s article_id=%s claims_passed=%s variations=%d",
            draft.id,
            article_id,
            claims_result.passed,
            len(variations),
            extra={
                "app_module": "content",
                "operation": "generate_draft",
                "correlation_id": corr,
                "organization_id": str(org_id),
                "outcome": "success",
            },
        )

        out = self._to_dict(draft, variations, claims_result)
        out["relevance_warning"] = relevance_warning
        out["article_status"] = article.status

        # Optional: brand kit can auto-queue LinkedIn image with the draft
        try:
            from app.modules.image.application.queue_generation import (
                load_brand_image_settings,
                queue_async_image_generation,
            )

            img_settings = await load_brand_image_settings(self._session, org_id)
            if img_settings.get("auto_generate_image_with_draft"):
                queued = await queue_async_image_generation(
                    self._session,
                    org_id=org_id,
                    draft_id=draft.id,
                    count=None,
                    reason="auto_with_draft",
                )
                out["image_generation"] = queued
                logger.info(
                    "Auto image queued with draft draft_id=%s count=%s",
                    draft.id,
                    queued.get("count"),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Auto image with draft skipped: %s", exc)

        return out

    def _to_dict(self, draft: Draft, variations: list, claims_result: object) -> dict:
        return {
            "id": str(draft.id),
            "article_id": str(draft.article_id) if draft.article_id else None,
            "content_type": draft.content_type,
            "status": draft.status,
            "generated_text": draft.generated_text,
            "edited_text": draft.edited_text,
            "hook": draft.hook,
            "cta": draft.cta,
            "hashtags": draft.hashtags_json,
            "metadata": draft.metadata_json,
            "version": draft.version,
            "variations": [
                {"index": i, "hook": v.get("hook", ""), "body": v.get("body", "")}
                for i, v in enumerate(variations)
            ],
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
        }


class ListDraftsUseCase:
    """List drafts for an organization, optionally filtered by status."""

    def __init__(self, session: AsyncSession) -> None:
        self._draft_repo = PgDraftRepository(session)
        self._session = session

    async def execute(self, org_id: uuid.UUID, status: str | None = None) -> list[dict]:
        drafts = await self._draft_repo.list_by_org(org_id, status=status)
        article_ids = [d.article_id for d in drafts if d.article_id]
        titles: dict[uuid.UUID, str] = {}
        if article_ids:
            result = await self._session.execute(
                select(Article.id, Article.title).where(Article.id.in_(article_ids))
            )
            titles = {row.id: row.title for row in result.all()}

        rows: list[dict] = []
        for d in drafts:
            text = d.edited_text or d.generated_text or ""
            article_title = titles.get(d.article_id) if d.article_id else None
            rows.append(
                {
                    "id": str(d.id),
                    "article_id": str(d.article_id) if d.article_id else None,
                    "article_title": article_title,
                    "title": d.hook or article_title or "Untitled draft",
                    "content_type": d.content_type,
                    "status": d.status,
                    "hook": d.hook,
                    "generated_text": d.generated_text,
                    "edited_text": d.edited_text,
                    "content": text,
                    "cta": d.cta,
                    "hashtags": d.hashtags_json or [],
                    "tone": d.content_type,
                    "word_count": len(text.split()) if text else 0,
                    "version": d.version,
                    "scheduled_for": (
                        (d.metadata_json or {}).get("scheduled_for")
                        if isinstance(d.metadata_json, dict)
                        else None
                    ),
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                }
            )
        return rows


class GetDraftUseCase:
    """Get a single draft with its variations (org-scoped)."""

    def __init__(self, session: AsyncSession) -> None:
        self._draft_repo = PgDraftRepository(session)
        self._variation_repo = PgDraftVariationRepository(session)
        self._session = session

    async def execute(self, org_id: uuid.UUID, draft_id: uuid.UUID) -> dict:
        draft = await self._draft_repo.get_by_id(draft_id, org_id=org_id)
        if draft is None:
            raise NotFoundError("Draft", str(draft_id))

        variations = await self._variation_repo.get_by_draft(draft_id)
        article = None
        source_name = None
        if draft.article_id:
            result = await self._session.execute(
                select(Article).where(Article.id == draft.article_id)
            )
            article = result.scalar_one_or_none()
            if article is not None:
                from app.infrastructure.postgres.models.news import NewsSource

                src = await self._session.execute(
                    select(NewsSource.name).where(NewsSource.id == article.source_id)
                )
                source_name = src.scalar_one_or_none()

        text = draft.edited_text or draft.generated_text or ""
        return {
            "id": str(draft.id),
            "article_id": str(draft.article_id) if draft.article_id else None,
            "article": (
                {
                    "id": str(article.id),
                    "title": article.title,
                    "summary": article.summary,
                    "url": article.url,
                    "source_name": source_name,
                    "published_at": article.published_at.isoformat()
                    if article.published_at
                    else None,
                    "category": article.category,
                }
                if article
                else None
            ),
            "content_type": draft.content_type,
            "status": draft.status,
            "title": draft.hook or (article.title if article else "Untitled draft"),
            "generated_text": draft.generated_text,
            "edited_text": draft.edited_text,
            "content": text,
            "hook": draft.hook,
            "cta": draft.cta,
            "hashtags": draft.hashtags_json,
            "tone": draft.content_type,
            "word_count": len(text.split()) if text else 0,
            "metadata": draft.metadata_json,
            "version": draft.version,
            "quality": (draft.metadata_json or {}).get("quality")
            if isinstance(draft.metadata_json, dict)
            else None,
            "visual_brief": (draft.metadata_json or {}).get("visual_brief")
            if isinstance(draft.metadata_json, dict)
            else None,
            "safety": (draft.metadata_json or {}).get("safety")
            if isinstance(draft.metadata_json, dict)
            else None,
            "draft_metadata": (draft.metadata_json or {}).get("draft_metadata")
            if isinstance(draft.metadata_json, dict)
            else None,
            "variations": [
                {
                    "index": v.variation_index,
                    "hook": v.hook,
                    "body": v.text,
                }
                for v in variations
            ],
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        }


class UpdateDraftUseCase:
    """Update a draft (edited_text only) — org-scoped."""

    def __init__(self, session: AsyncSession) -> None:
        self._draft_repo = PgDraftRepository(session)

    async def execute(self, org_id: uuid.UUID, draft_id: uuid.UUID, edited_text: str) -> dict:
        draft = await self._draft_repo.get_by_id(draft_id, org_id=org_id)
        if draft is None:
            raise NotFoundError("Draft", str(draft_id))

        await self._draft_repo.update(draft_id, {"edited_text": edited_text}, org_id=org_id)
        draft = await self._draft_repo.get_by_id(draft_id, org_id=org_id)

        return {
            "id": str(draft.id),  # type: ignore[union-attr]
            "status": draft.status,  # type: ignore[union-attr]
            "generated_text": draft.generated_text,  # type: ignore[union-attr]
            "edited_text": draft.edited_text,  # type: ignore[union-attr]
            "hook": draft.hook,  # type: ignore[union-attr]
            "version": draft.version,  # type: ignore[union-attr]
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,  # type: ignore[union-attr]
        }


class DeleteDraftUseCase:
    """Permanently delete a draft — org-scoped. Images/jobs are left as-is."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._draft_repo = PgDraftRepository(session)

    async def execute(self, org_id: uuid.UUID, draft_id: uuid.UUID) -> dict:
        draft = await self._draft_repo.get_by_id(draft_id, org_id=org_id)
        if draft is None:
            raise NotFoundError("Draft", str(draft_id))

        await self._session.execute(delete(DraftVersion).where(DraftVersion.draft_id == draft_id))
        await self._session.execute(delete(DraftVariation).where(DraftVariation.draft_id == draft_id))
        await self._session.execute(delete(PromptHistory).where(PromptHistory.draft_id == draft_id))
        await self._session.execute(
            update(GenerationReplay)
            .where(GenerationReplay.draft_id == draft_id)
            .values(draft_id=None)
        )
        await self._session.execute(
            update(CaptureSession)
            .where(CaptureSession.draft_id == draft_id)
            .values(draft_id=None)
        )
        await self._session.execute(delete(Draft).where(Draft.id == draft_id))
        await self._session.flush()

        return {"id": str(draft_id), "deleted": True}


class RegenerateDraftSectionUseCase:
    """Regenerate the full post or a section, with optional client guidance."""

    def __init__(
        self, session: AsyncSession, orchestrator: AIOrchestrator | None = None
    ) -> None:
        self._session = session
        self._draft_repo = PgDraftRepository(session)
        orch = orchestrator or AIOrchestratorFactory.create()
        consensus = None
        from app.core.config import get_settings

        if get_settings().CONSENSUS_ENABLED:
            from app.modules.consensus.application.factory import ConsensusEngineFactory

            consensus = ConsensusEngineFactory.create(orchestrator=orch)
        self._engine = DefaultContentGenerationEngine(orch, consensus_engine=consensus)
        self._regen = DefaultDraftRegenerator(orch, self._engine)

    async def execute(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        section: str = "full",
        guidance: str | None = None,
    ) -> dict:
        from app.core.logging import get_logger
        from app.modules.content.application.generation.regenerator import (
            resolve_regen_section,
        )

        try:
            resolved = resolve_regen_section(section or "full", guidance or "")
            sec = RegenSection(resolved)
        except ValueError as exc:
            raise NotFoundError("RegenSection", section) from exc

        if (section or "full") == "full" and sec.value != "full" and (guidance or "").strip():
            get_logger(__name__).info(
                "regen.section_resolved from=full to=%s guidance=%s",
                sec.value,
                (guidance or "")[:80],
            )

        draft = await self._draft_repo.get_by_id(draft_id, org_id=org_id)
        if draft is None:
            raise NotFoundError("Draft", str(draft_id))

        previous = {
            "version": draft.version or 1,
            "hook": draft.hook or "",
            "body": draft.edited_text or draft.generated_text or "",
            "cta": draft.cta or "",
            "hashtags": list(draft.hashtags_json or []),
            "status": draft.status,
        }

        self._session.add(
            DraftVersion(
                draft_id=draft_id,
                version=draft.version or 1,
                text=(
                    f"{draft.hook or ''}\n\n{draft.edited_text or draft.generated_text or ''}"
                    f"\n\n{draft.cta or ''}"
                ).strip(),
                change_summary="snapshot_before_regen",
                draft_json={
                    "hook": draft.hook,
                    "body": draft.edited_text or draft.generated_text,
                    "cta": draft.cta,
                    "hashtags": draft.hashtags_json,
                },
            )
        )

        structured = StructuredDraft(
            hook=draft.hook or "",
            body=draft.edited_text or draft.generated_text or "",
            cta=draft.cta or "",
            hashtags=tuple(draft.hashtags_json or ()),
            content_type=draft.content_type,
            content_plan_id=str(draft.content_plan_id or ""),
            prompt_version=draft.prompt_version or "",
            metadata=dict(draft.metadata_json or {}),
            markdown=draft.generated_text or "",
        )
        source = str((draft.metadata_json or {}).get("source_text") or "")
        updated = await self._regen.regenerate(
            structured,
            sec,
            source_text=source,
            organization_id=org_id,
            guidance=(guidance or "").strip(),
        )

        new_version = (draft.version or 1) + 1
        fields = {
            "hook": updated.hook,
            "generated_text": updated.body,
            "edited_text": None,
            "cta": updated.cta,
            "hashtags_json": list(updated.hashtags),
            "version": new_version,
            "status": "pending_review",
            "metadata_json": {
                **(draft.metadata_json or {}),
                **updated.metadata,
                "quality": updated.quality.to_dict()
                if updated.quality is not None and hasattr(updated.quality, "to_dict")
                else updated.metadata.get("quality"),
                "visual_brief": updated.visual_brief.to_dict()
                if updated.visual_brief is not None
                and hasattr(updated.visual_brief, "to_dict")
                else updated.metadata.get("visual_brief"),
                "safety": updated.safety.to_dict()
                if updated.safety is not None and hasattr(updated.safety, "to_dict")
                else updated.metadata.get("safety"),
                "draft_metadata": updated.draft_metadata.to_dict()
                if updated.draft_metadata is not None
                and hasattr(updated.draft_metadata, "to_dict")
                else updated.metadata.get("draft_metadata"),
                "regenerated_section": sec.value,
                "regen_guidance": (guidance or "").strip() or None,
                "previous_version": previous,
            },
            "quality_score": updated.quality_score,
            "draft_json": updated.to_dict(),
        }
        if hasattr(draft, "quality_breakdown_json"):
            fields["quality_breakdown_json"] = fields["metadata_json"].get("quality")
        if hasattr(draft, "visual_brief_json"):
            fields["visual_brief_json"] = fields["metadata_json"].get("visual_brief")
        if hasattr(draft, "safety_json"):
            fields["safety_json"] = fields["metadata_json"].get("safety")
        if hasattr(draft, "draft_metadata_json"):
            fields["draft_metadata_json"] = fields["metadata_json"].get("draft_metadata")

        await self._draft_repo.update(draft_id, fields, org_id=org_id)
        self._session.add(
            DraftVersion(
                draft_id=draft_id,
                version=new_version,
                text=updated.markdown or updated.body,
                change_summary=f"regenerated:{sec.value}"
                + (f":{(guidance or '')[:80]}" if guidance else ""),
                draft_json=updated.to_dict(),
            )
        )
        await self._session.flush()
        refreshed = await self._draft_repo.get_by_id(draft_id, org_id=org_id)
        current = {
            "version": new_version,
            "hook": refreshed.hook if refreshed else updated.hook,
            "body": refreshed.generated_text if refreshed else updated.body,
            "cta": refreshed.cta if refreshed else updated.cta,
            "hashtags": refreshed.hashtags_json if refreshed else list(updated.hashtags),
            "status": refreshed.status if refreshed else "pending_review",
        }
        return {
            "id": str(draft_id),
            "section": sec.value,
            "guidance": (guidance or "").strip() or None,
            "version": new_version,
            "status": current["status"],
            "hook": current["hook"],
            "cta": current["cta"],
            "hashtags": current["hashtags"],
            "generated_text": current["body"],
            "previous": previous,
            "current": current,
            "metadata": refreshed.metadata_json if refreshed else fields["metadata_json"],
            "quality": fields["metadata_json"].get("quality"),
            "visual_brief": fields["metadata_json"].get("visual_brief"),
            "safety": fields["metadata_json"].get("safety"),
            "message": (
                "Hook updated — body and CTA kept."
                if sec.value == "hook"
                else "Body rewritten — hook and CTA kept."
                if sec.value == "body"
                else "CTA updated."
                if sec.value == "cta"
                else "Post regenerated. Compare previous vs new, then approve or reject."
            ),
        }


class ListDraftVersionsUseCase:
    """List saved draft versions for before/after review."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._draft_repo = PgDraftRepository(session)

    async def execute(self, org_id: uuid.UUID, draft_id: uuid.UUID) -> dict:
        draft = await self._draft_repo.get_by_id(draft_id, org_id=org_id)
        if draft is None:
            raise NotFoundError("Draft", str(draft_id))
        rows = (
            await self._session.execute(
                select(DraftVersion)
                .where(DraftVersion.draft_id == draft_id)
                .order_by(DraftVersion.version.desc())
                .limit(20)
            )
        ).scalars().all()
        items = [
            {
                "id": str(r.id),
                "version": r.version,
                "text": r.text,
                "change_summary": r.change_summary,
                "draft_json": r.draft_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return {
            "draft_id": str(draft_id),
            "current_version": draft.version,
            "items": items,
            "count": len(items),
        }
