"""IntelligenceWorkflow — orchestrates score → update status."""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ArticleStatus
from app.core.logging import get_logger
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.ai.domain.ports import AIOrchestrator
from app.infrastructure.postgres.models.news import Article
from app.modules.intelligence.application.scorer import RelevanceScorer

logger = get_logger(__name__)


class IntelligenceWorkflow:
    """For a given article_id: score → update status."""

    def __init__(
        self,
        session: AsyncSession,
        orchestrator: AIOrchestrator | None = None,
    ) -> None:
        self._session = session
        orch = orchestrator or AIOrchestratorFactory.create()
        self._scorer = RelevanceScorer(session, orch)

    async def run(self, org_id: uuid.UUID, article_id: uuid.UUID) -> dict:
        """Execute the intelligence pipeline for a single article.

        Returns a summary dict with score and status.
        """
        from sqlalchemy import select

        stmt = select(Article).where(Article.id == article_id)
        result = await self._session.execute(stmt)
        article = result.scalar_one_or_none()

        if article is None:
            raise ValueError(f"Article {article_id} not found")

        score_result = await self._scorer.score(
            org_id=org_id,
            article_id=article_id,
            title=article.title,
            summary=article.summary or "",
            body_text=article.body_text or "",
        )

        new_status = _resolve_article_status(score_result.score)
        await self._update_article_status(article_id, new_status)
        await self._merge_score_json(article, score_result)

        logger.info(
            "Intelligence workflow complete: article=%s score=%d status=%s",
            article_id,
            score_result.score,
            new_status,
        )

        return {
            "article_id": str(article_id),
            "score": score_result.score,
            "status": new_status,
            "sector": score_result.sector,
            "framework": score_result.framework,
            "angle": score_result.angle,
            "reason": score_result.reason,
        }

    async def _merge_score_json(self, article: Article, score_result) -> None:
        """Merge AI relevance into score_json without dropping sentiment."""
        existing = dict(article.score_json) if isinstance(article.score_json, dict) else {}
        existing.update(
            {
                "ai_relevance": score_result.score,
                "relevance": score_result.score,
                "sector": score_result.sector,
                "framework": score_result.framework,
                "angle": score_result.angle,
                "reason": score_result.reason,
            }
        )
        stmt = (
            update(Article)
            .where(Article.id == article.id)
            .values(score_json=existing)
        )
        await self._session.execute(stmt)

    async def _update_article_status(self, article_id: uuid.UUID, status: str) -> None:
        stmt = update(Article).where(Article.id == article_id).values(status=status)
        await self._session.execute(stmt)


# Relevance auto-classify threshold (1–5 AI score from brand profile).
# 2+ = relevant so solid cyber/IT/compliance stories are kept, not only perfect fits.
_RELEVANT_MIN_SCORE = 2


def _resolve_article_status(ai_score: int) -> str:
    """Hard auto-segregation from brand-profile scoring — no manual-review bucket.

    Trusts the AI score directly (score >= 2 → relevant, else irrelevant). The
    profile prompt already instructs the model to score generously for anything
    in-scope, so a secondary keyword override isn't just redundant — it flips
    articles the model deliberately scored 1 for well-reasoned cause (wrong
    country, wrong sector, no actionable angle) purely because a generic term
    like "ransomware" or "CVE-" appears in the headline. Admin thumbs can still
    override and teach the brand profile.
    """
    if int(ai_score or 0) >= _RELEVANT_MIN_SCORE:
        return ArticleStatus.RELEVANT
    return ArticleStatus.IRRELEVANT
