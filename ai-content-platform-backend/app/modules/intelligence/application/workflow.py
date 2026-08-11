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

        in_scope = await self._brand_in_scope_terms(org_id)
        effective = _effective_ai_score(article, score_result.score, in_scope_terms=in_scope)
        new_status = _resolve_article_status(
            article, score_result.score, in_scope_terms=in_scope
        )
        await self._update_article_status(article_id, new_status)
        await self._merge_score_json(article, score_result, effective_score=effective)

        logger.info(
            "Intelligence workflow complete: article=%s score=%d effective=%d status=%s",
            article_id,
            score_result.score,
            effective,
            new_status,
        )

        return {
            "article_id": str(article_id),
            "score": effective,
            "raw_score": score_result.score,
            "status": new_status,
            "sector": score_result.sector,
            "framework": score_result.framework,
            "angle": score_result.angle,
            "reason": score_result.reason,
        }

    async def _merge_score_json(
        self, article: Article, score_result, *, effective_score: int | None = None
    ) -> None:
        """Merge AI relevance into score_json without dropping sentiment."""
        existing = dict(article.score_json) if isinstance(article.score_json, dict) else {}
        stored = int(effective_score if effective_score is not None else score_result.score)
        existing.update(
            {
                "ai_relevance": stored,
                "relevance": stored,
                "ai_relevance_raw": score_result.score,
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

    async def _brand_in_scope_terms(self, org_id: uuid.UUID) -> tuple[str, ...]:
        try:
            from app.modules.brand_intelligence.application.news_policy_service import (
                BrandNewsPolicyService,
            )

            policy = await BrandNewsPolicyService(self._session).get_for_org(org_id)
            if policy.in_scope_terms:
                return tuple(policy.in_scope_terms)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Brand in-scope terms unavailable: %s", exc)
        return _DEFAULT_IN_SCOPE_TERMS


# Relevance auto-classify threshold (1–5 AI score from brand profile).
# 2+ = relevant so solid cyber/IT/compliance stories are kept, not only perfect fits.
_RELEVANT_MIN_SCORE = 2

# Fallback in-scope signals when BrandNewsPolicy is unavailable.
_DEFAULT_IN_SCOPE_TERMS = (
    "cyber",
    "ransomware",
    "phishing",
    "malware",
    "breach",
    "data protection",
    "gdpr",
    "cyber essentials",
    "dspt",
    "cqc",
    "microsoft 365",
    "m365",
    "entra",
    "mfa",
    "multi-factor",
    "zero trust",
    "endpoint",
    "edr",
    "firewall",
    "vpn",
    "it support",
    "managed service",
    "msp",
    "infosec",
    "information security",
    "ico fine",
    "ico ",
    "credential",
    "business email",
    "bec",
    "vulnerability",
    "cve-",
    "patch tuesday",
    "backup",
    "disaster recovery",
)


def _text_looks_in_scope(article: Article, terms: tuple[str, ...] | list[str]) -> bool:
    blob = f"{article.title or ''} {article.summary or ''} {article.category or ''}".lower()
    return any(term.lower() in blob for term in terms if term)


def _effective_ai_score(
    article: Article,
    ai_score: int,
    *,
    in_scope_terms: tuple[str, ...] | list[str] | None = None,
) -> int:
    """Prefer AI score; boost brand in-scope headlines the model scored too low."""
    score = int(ai_score or 0)
    terms = in_scope_terms or _DEFAULT_IN_SCOPE_TERMS
    if score < _RELEVANT_MIN_SCORE and _text_looks_in_scope(article, terms):
        return _RELEVANT_MIN_SCORE
    return score


def _resolve_article_status(
    article: Article,
    ai_score: int,
    *,
    in_scope_terms: tuple[str, ...] | list[str] | None = None,
) -> str:
    """Hard auto-segregation from brand-profile scoring — no manual-review bucket.

    - effective score >= 2 → relevant
    - else → irrelevant
    Admin thumbs can still override and teach the brand profile.
    """
    if _effective_ai_score(article, ai_score, in_scope_terms=in_scope_terms) >= _RELEVANT_MIN_SCORE:
        return ArticleStatus.RELEVANT
    return ArticleStatus.IRRELEVANT
