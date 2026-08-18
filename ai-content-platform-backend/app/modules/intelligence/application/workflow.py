"""IntelligenceWorkflow — orchestrates score → update status."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ArticleStatus
from app.core.logging import get_logger
from app.modules.ai.application.factory import AIOrchestratorFactory
from app.modules.ai.domain.ports import AIOrchestrator
from app.infrastructure.postgres.models.news import Article, NewsSource
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
        stmt = select(Article).where(Article.id == article_id)
        result = await self._session.execute(stmt)
        article = result.scalar_one_or_none()

        if article is None:
            raise ValueError(f"Article {article_id} not found")

        source = await self._session.get(NewsSource, article.source_id)

        score_result = await self._scorer.score(
            org_id=org_id,
            article_id=article_id,
            title=article.title,
            summary=article.summary or "",
            body_text=article.body_text or "",
            published_at=article.published_at,
            source_name=source.name if source else None,
        )
        await self._apply_local_editorial_guards(org_id, article, score_result)

        new_status = _resolve_article_status(
            score_result.score, decision=score_result.decision
        )
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
            "decision": score_result.decision,
            "article_type": score_result.article_type,
            "quality": score_result.quality_scores or {},
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
                "decision": score_result.decision,
                "article_type": score_result.article_type,
                "quality": score_result.quality_scores or {},
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

    async def _apply_local_editorial_guards(
        self,
        org_id: uuid.UUID,
        article: Article,
        score_result,
    ) -> None:
        """Downgrade obvious editorial failures without withholding the LLM call.

        The LLM still evaluates every article. These local checks protect the
        final feed against facts the model cannot reliably infer in isolation
        (already drafted or duplicate history) and deterministic low-quality
        cases (stale/thin records). No internal editorial history is sent to an
        external provider.
        """
        if (score_result.decision or "").lower() not in {"relevant", "recommended"}:
            return

        reasons: list[str] = []
        quality = score_result.quality_scores or {}
        now = datetime.now(timezone.utc)
        if article.published_at is not None:
            published = article.published_at
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published < now - timedelta(days=90):
                reasons.append("older than 90 days and not suitable as current news")
                quality["freshness"] = min(quality.get("freshness", 1), 2)

        substance = " ".join(
            value.strip()
            for value in (article.summary or "", article.body_text or "")
            if value and value.strip()
        )
        if len(substance) < 160:
            reasons.append("the stored article has too little substance for a standalone educational post")
            quality["educational_value"] = min(quality.get("educational_value", 1), 2)

        from app.infrastructure.postgres.models.content import Draft

        already_drafted = (
            await self._session.execute(
                select(Draft.id)
                .where(
                    Draft.organization_id == org_id,
                    Draft.article_id == article.id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if already_drafted is not None:
            reasons.append("a draft already exists for this article")

        recent_titles = (
            await self._session.execute(
                select(Article.title)
                .where(
                    Article.organization_id == org_id,
                    Article.id != article.id,
                    Article.status.in_(("relevant", "reference", "used")),
                    Article.updated_at >= now - timedelta(days=120),
                )
                .order_by(Article.updated_at.desc())
                .limit(80)
            )
        ).scalars().all()
        if any(_same_story(article.title, other) for other in recent_titles):
            reasons.append("substantially duplicates a recently retained story")
            quality["distinctiveness"] = min(quality.get("distinctiveness", 1), 2)

        if not reasons:
            return
        score_result.decision = "rejected"
        score_result.article_type = "reject"
        score_result.score = min(int(score_result.score or 1), 3)
        score_result.quality_scores = quality
        suffix = "; ".join(reasons)
        score_result.reason = f"{score_result.reason or 'Downgraded by editorial safeguards'}; {suffix}."


_TITLE_STOP_WORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on",
    "the", "to", "with", "new", "report", "analysis", "security", "cyber",
}


def _title_tokens(title: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9-]+", (title or "").lower())
        if len(token) > 2 and token not in _TITLE_STOP_WORDS
    }


def _same_story(left: str, right: str) -> bool:
    """Conservative local title match; false positives are worse than misses."""
    left_cves = set(re.findall(r"cve-\d{4}-\d+", (left or "").lower()))
    right_cves = set(re.findall(r"cve-\d{4}-\d+", (right or "").lower()))
    if left_cves and left_cves.intersection(right_cves):
        return True
    a = _title_tokens(left)
    b = _title_tokens(right)
    if len(a) < 4 or len(b) < 4:
        return False
    return len(a & b) / len(a | b) >= 0.72


# The original accepted-news benchmark retained score-3 items when they passed
# all four relevance tests. Scores 1-2 and explicit model rejections stay out.
_RELEVANT_MIN_SCORE = 3


def _resolve_article_status(ai_score: int, *, decision: str | None = None) -> str:
    """Map the binary editorial decision to relevant/rejected storage states."""
    score = int(ai_score or 0)
    normalized = (decision or "").strip().lower()
    if normalized in {"relevant", "recommended"} and score >= _RELEVANT_MIN_SCORE:
        return ArticleStatus.RELEVANT
    return ArticleStatus.IRRELEVANT
