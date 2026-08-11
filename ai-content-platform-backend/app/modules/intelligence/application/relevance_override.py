"""Admin relevance override — updates article status and records learning signals."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ArticleStatus, MembershipRole
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.infrastructure.postgres.models.learning import Rule, WritingPreference
from app.infrastructure.postgres.models.news import Article, SourceFeedbackEventRow

logger = get_logger(__name__)

_ALLOWED = {
    "relevant": ArticleStatus.RELEVANT,
    "irrelevant": ArticleStatus.IRRELEVANT,
    "scored": ArticleStatus.SCORED,
    ArticleStatus.RELEVANT: ArticleStatus.RELEVANT,
    ArticleStatus.IRRELEVANT: ArticleStatus.IRRELEVANT,
    ArticleStatus.SCORED: ArticleStatus.SCORED,
}


class SetArticleRelevanceUseCase:
    """Let an editor/admin override AI relevance and teach the learning library."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        *,
        org_id: uuid.UUID,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        status: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if role not in (
            MembershipRole.OWNER,
            MembershipRole.EDITOR,
            "owner",
            "editor",
            "admin",
        ):
            raise AuthorizationError("Only editors/admins can override relevance")

        new_status = _ALLOWED.get(status)
        if new_status is None:
            raise ValidationError(
                "status must be one of: relevant, irrelevant, scored"
            )

        article = (
            await self._session.execute(
                select(Article).where(
                    Article.id == article_id,
                    Article.organization_id == org_id,
                )
            )
        ).scalar_one_or_none()
        if article is None:
            raise NotFoundError("Article", str(article_id))

        previous = article.status
        score = dict(article.score_json) if isinstance(article.score_json, dict) else {}
        score["admin_override"] = {
            "status": new_status,
            "previous_status": previous,
            "note": (note or "").strip() or None,
            "user_id": str(user_id),
        }
        # Mirror a synthetic AI score so UI score + filters stay consistent
        if new_status == ArticleStatus.RELEVANT:
            score["ai_relevance"] = max(int(score.get("ai_relevance") or 0), 4)
            score["relevance"] = score["ai_relevance"]
        elif new_status == ArticleStatus.IRRELEVANT:
            score["ai_relevance"] = 1
            score["relevance"] = 1
        else:
            score["ai_relevance"] = max(int(score.get("ai_relevance") or 0), 2)
            score["relevance"] = score["ai_relevance"]

        article.status = new_status
        article.score_json = score

        # Durable feedback row for analytics
        self._session.add(
            SourceFeedbackEventRow(
                organization_id=org_id,
                source_id=str(article.source_id),
                kind="relevance_override",
                weight=1.0 if new_status == ArticleStatus.RELEVANT else -1.0,
                article_id=str(article.id),
                metadata_json={
                    "status": new_status,
                    "previous_status": previous,
                    "note": note,
                    "title": article.title,
                    "category": article.category,
                },
            )
        )

        # Learning: preference + brand profile memory so future auto-scoring improves
        learned = await self._record_learning(
            org_id=org_id,
            article=article,
            new_status=new_status,
            note=note,
        )

        profile_updated = False
        if new_status in (ArticleStatus.RELEVANT, ArticleStatus.IRRELEVANT):
            from app.modules.organization.application.client_profile import (
                append_admin_feedback_to_profile,
            )

            profile_updated = await append_admin_feedback_to_profile(
                self._session,
                org_id,
                relevant=new_status == ArticleStatus.RELEVANT,
                title=article.title or "",
                category=article.category,
                note=note,
            )

        await self._session.flush()
        logger.info(
            "relevance.override article=%s %s→%s by=%s profile=%s",
            article_id,
            previous,
            new_status,
            user_id,
            profile_updated,
        )
        return {
            "id": str(article.id),
            "status": article.status,
            "previous_status": previous,
            "score_json": article.score_json,
            "learned": learned,
            "brand_profile_updated": profile_updated,
        }

    async def _record_learning(
        self,
        *,
        org_id: uuid.UUID,
        article: Article,
        new_status: str,
        note: str | None,
    ) -> dict[str, Any]:
        title = (article.title or "")[:200]
        category = article.category or "general"
        note_bit = f" Admin note: {note.strip()}" if note and note.strip() else ""

        if new_status == ArticleStatus.RELEVANT:
            pref_text = (
                f"Treat stories like “{title}” (topic: {category}) as relevant "
                f"for Guard IQ LinkedIn posts.{note_bit}"
            )
            rule_text = None
            rule_category = None
        elif new_status == ArticleStatus.IRRELEVANT:
            pref_text = (
                f"Do not prioritize stories like “{title}” (topic: {category}) "
                f"for Guard IQ posts.{note_bit}"
            )
            rule_text = (
                f"Skip or down-rank articles similar to: {title} "
                f"(category={category}).{note_bit}"
            )
            rule_category = "relevance"
        else:
            pref_text = (
                f"Stories like “{title}” need human review before drafting.{note_bit}"
            )
            rule_text = None
            rule_category = None

        pref = WritingPreference(
            organization_id=org_id,
            category="relevance",
            preference=pref_text,
            source_type="admin_override",
            is_active=True,
            lifecycle="approved",
            confidence=0.9,
            created_from_review=False,
        )
        self._session.add(pref)

        rule_id = None
        if rule_text and rule_category:
            rule = Rule(
                organization_id=org_id,
                category=rule_category,
                text=rule_text,
                is_active=True,
                lifecycle="approved",
                priority=10,
                confidence=0.85,
                created_from_review=False,
            )
            self._session.add(rule)
            await self._session.flush()
            rule_id = str(rule.id)

        await self._session.flush()
        return {
            "preference_id": str(pref.id),
            "rule_id": rule_id,
            "preference": pref_text,
        }
