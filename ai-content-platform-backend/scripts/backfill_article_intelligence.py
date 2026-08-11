"""Backfill sentiment + AI relevance for existing articles.

Usage (from backend venv):
  python scripts/backfill_article_intelligence.py [--limit 30]
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select


async def main(limit: int) -> None:
    from app.infrastructure.postgres.models.news import Article
    from app.infrastructure.postgres.session import async_session_factory
    from app.modules.ai.application.factory import AIOrchestratorFactory
    from app.modules.intelligence.application.workflow import IntelligenceWorkflow
    from app.modules.news.application.sentiment import analyze_sentiment
    from app.modules.news.domain.models import CanonicalArticle

    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(Article)
                .order_by(Article.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()

        print(f"Processing {len(rows)} articles…")
        sentiment_ok = 0
        relevance_ok = 0
        relevance_fail = 0

        for article in rows:
            # Sentiment (lexicon — fast)
            canon = CanonicalArticle(
                title=article.title or "",
                url=article.url or "",
                summary=article.summary or "",
                body_text=article.body_text or "",
                published_at=article.published_at or datetime.now(timezone.utc),
            )
            sent = analyze_sentiment(canon)
            score = dict(article.score_json) if isinstance(article.score_json, dict) else {}
            score["sentiment"] = sent.to_dict()
            article.score_json = score
            sentiment_ok += 1

        await session.commit()
        print(f"Sentiment updated: {sentiment_ok}")

        # Relevance (LLM — slower). Re-open session per article for isolation.
        for article in rows:
            try:
                async with async_session_factory() as s2:
                    wf = IntelligenceWorkflow(s2, AIOrchestratorFactory.create())
                    result = await wf.run(
                        org_id=article.organization_id,
                        article_id=article.id,
                    )
                    await s2.commit()
                    relevance_ok += 1
                    print(
                        f"  relevance {article.id} → score={result.get('score')} "
                        f"status={result.get('status')}"
                    )
            except Exception as exc:
                relevance_fail += 1
                print(f"  relevance FAIL {article.id}: {exc}")

        print(
            f"Done. sentiment={sentiment_ok} relevance_ok={relevance_ok} "
            f"relevance_fail={relevance_fail}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    asyncio.run(main(args.limit))
