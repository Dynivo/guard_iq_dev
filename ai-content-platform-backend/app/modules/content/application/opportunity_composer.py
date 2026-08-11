"""Opportunity composition — deterministic ranking into business DTOs (Phase 1)."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ArticleStatus, DraftStatus
from app.core.logging import get_logger
from app.infrastructure.postgres.models.branding import BrandKit
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.intelligence import RelevanceScore
from app.infrastructure.postgres.models.news import Article, NewsSource
from app.modules.content.application.publishing_plan import (
    PublishingPlanService,
    fortnight_window,
)
from app.modules.news.infrastructure.enrichment_store import list_org_trends

logger = get_logger(__name__)

_CONFIG_PATH = (
    Path(__file__).resolve().parents[4] / "configs" / "content" / "opportunity_ranking.yaml"
)

_WORD_RE = re.compile(r"[a-z0-9]{3,}")

LIFECYCLE_STAGES = (
    "discovered",
    "scored",
    "recommended",
    "generated",
    "reviewed",
    "approved",
    "published",
    "learning_updated",
)


@lru_cache(maxsize=1)
def load_opportunity_ranking_config() -> dict[str, Any]:
    if not _CONFIG_PATH.is_file():
        return {
            "weights": {
                "relevance": 0.35,
                "opportunity_tags": 0.15,
                "trend": 0.15,
                "freshness": 0.15,
                "audience_fit": 0.10,
                "competition": 0.10,
            },
            "angle_map": {},
            "default_strategic_goal": (
                "Become a trusted authority in your market through "
                "consistent, high-signal LinkedIn content."
            ),
            "memory_gap_days": 14,
            "competition_soft_cap": 3,
        }
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def title_similarity(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def opportunity_id_for(article_ids: list[uuid.UUID]) -> str:
    raw = ",".join(sorted(str(i) for i in article_ids))
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"opp_{digest}"


def publisher_from_article(article: Article, source: NewsSource | None) -> str:
    if source and source.name:
        return source.name
    if article.author:
        return article.author
    try:
        host = urlparse(article.url or "").netloc
        return host.replace("www.", "") if host else "Unknown"
    except Exception:  # noqa: BLE001
        return "Unknown"


def extract_opportunity_tags(article: Article) -> list[str]:
    meta = article.metadata_json if isinstance(article.metadata_json, dict) else {}
    raw = meta.get("opportunities") or meta.get("opportunity_tags") or []
    if isinstance(raw, dict):
        # OpportunitySignals style
        tags = raw.get("tags") or raw.get("types") or list(raw.keys())
        return [str(t) for t in tags]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict) and item.get("type"):
                out.append(str(item["type"]))
        return out
    return []


def compute_confidence_factors(
    *,
    relevance: int | None,
    tags: list[str],
    tag_weights: dict[str, float],
    trend_score: float,
    age_hours: float | None,
    audience: str | None,
    competition_count: int,
    soft_cap: int,
    weights: dict[str, float],
    brand_topic_overlap: float = 0.0,
) -> dict[str, int]:
    """Return factor scores 0–100 plus composite (Estimated)."""
    rel = float(relevance if relevance is not None else 40)
    # relevance often 0–100 already
    if rel <= 1:
        rel *= 100

    tag_boost = 0.0
    for t in tags:
        tag_boost += float(tag_weights.get(t, 0.05)) * 100
    tag_score = min(100.0, 40 + tag_boost)

    trend = clamp_score(trend_score * 100 if trend_score <= 1 else trend_score)

    if age_hours is None:
        freshness = 70
    elif age_hours <= 24:
        freshness = 96
    elif age_hours <= 72:
        freshness = 85
    elif age_hours <= 168:
        freshness = 70
    else:
        freshness = 45

    audience_fit = 88 if audience else 55
    overlap = max(0.0, min(1.0, float(brand_topic_overlap or 0.0)))
    cfg_boost = float(load_opportunity_ranking_config().get("audience_topic_boost") or 0.0)
    # Prefer brand YAML boost if present; else use opportunity_ranking default 0
    try:
        from app.modules.brand_intelligence.application.news_policy_service import (
            load_news_policy_config,
        )

        cfg_boost = float(
            (load_news_policy_config() or {}).get("audience_topic_boost", cfg_boost) or cfg_boost
        )
    except Exception:  # noqa: BLE001
        pass
    audience_fit = clamp_score(audience_fit + overlap * (cfg_boost * 100 if cfg_boost <= 1 else cfg_boost))
    # Lower competition score when many similar recent posts
    if competition_count <= 0:
        competition = 90
    elif competition_count >= soft_cap:
        competition = 45
    else:
        competition = clamp_score(90 - competition_count * (45 / soft_cap))

    timing = clamp_score((freshness * 0.6) + (trend * 0.4))
    authority = clamp_score((rel * 0.5) + (tag_score * 0.3) + (audience_fit * 0.2))

    w = weights
    composite = (
        rel * float(w.get("relevance", 0.35))
        + tag_score * float(w.get("opportunity_tags", 0.15))
        + trend * float(w.get("trend", 0.15))
        + freshness * float(w.get("freshness", 0.15))
        + audience_fit * float(w.get("audience_fit", 0.10))
        + competition * float(w.get("competition", 0.10))
    )

    return {
        "composite": clamp_score(composite),
        "trend": clamp_score(trend),
        "audience_fit": clamp_score(audience_fit),
        "authority": clamp_score(authority),
        "timing": clamp_score(timing),
        "competition": clamp_score(competition),
        "freshness": clamp_score(freshness),
    }


def build_recommendation(confidence: dict[str, int], why_selected: list[str]) -> dict[str, Any]:
    score = confidence["composite"]
    stars = 5 if score >= 90 else 4 if score >= 75 else 3 if score >= 60 else 2 if score >= 40 else 1
    why: list[str] = []
    if confidence["authority"] >= 80:
        why.append("High authority")
    if confidence["audience_fit"] >= 70:
        why.append("High relevance")
    if confidence["competition"] >= 75:
        why.append("Low competition")
    if confidence["trend"] >= 70:
        why.append("Trending")
    if confidence["freshness"] >= 85:
        why.append("Fresh story")
    if not why:
        why = why_selected[:3] or ["Fits content mix"]
    return {
        "should_generate": score >= 55,
        "stars": stars,
        "why": why[:5],
        "estimated_read_minutes": 3 if score >= 70 else 5,
        "editing_effort": "low" if score >= 80 else "medium" if score >= 60 else "high",
    }


def timeline_bucket_for(
    *,
    freshness: int,
    trend: int,
    age_hours: float | None,
) -> tuple[str, str]:
    """Return (bucket, timing_advice)."""
    if age_hours is not None and age_hours < 12 and trend >= 75:
        return "today", "Post today — story is peaking"
    if freshness >= 85 and trend >= 60:
        return "today", "Post today — high freshness and trend"
    if trend >= 80 and freshness < 70:
        return "this_week", "Wait — story is still evolving; revisit tomorrow"
    if freshness >= 60:
        return "this_week", "Schedule this week while relevant"
    return "later", "Lower urgency — save for later if mix allows"


def map_angles(tags: list[str], angle_map: dict[str, str]) -> tuple[str, list[str]]:
    mapped = []
    for t in tags:
        label = angle_map.get(t) or t.replace("_", " ").title()
        if label not in mapped:
            mapped.append(label)
    if not mapped:
        mapped = ["Educational"]
    primary = mapped[0]
    alts = mapped[1:5] or ["Checklist", "Myth vs Fact", "Opinion"]
    # Ensure alts don't duplicate primary
    alts = [a for a in alts if a != primary][:4]
    if not alts:
        alts = ["Checklist", "Myth vs Fact"]
    return primary, alts


def lifecycle_for_article(
    article_id: uuid.UUID,
    drafts_by_article: dict[uuid.UUID, Draft],
) -> str:
    draft = drafts_by_article.get(article_id)
    if draft is None:
        return "recommended"
    status = (draft.status or "").lower()
    meta = draft.metadata_json if isinstance(draft.metadata_json, dict) else {}
    if status == DraftStatus.PUBLISHED or status == "published":
        return "published"
    if status == DraftStatus.APPROVED or status == "approved":
        if meta.get("scheduled_for"):
            return "approved"
        return "approved"
    if status in (DraftStatus.PENDING_REVIEW, DraftStatus.IN_REVIEW, "pending_review", "in_review"):
        return "reviewed"
    if status in (DraftStatus.DRAFT, DraftStatus.GENERATING, "draft", "generating"):
        return "generated"
    return "scored"


class OpportunityComposerService:
    """Compose Opportunity business DTOs + Daily Briefing + Strategist payload."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cfg = load_opportunity_ranking_config()

    async def list_opportunities(
        self,
        org_id: uuid.UUID,
        *,
        limit: int = 30,
        include_ignored: bool = False,
    ) -> list[dict[str, Any]]:
        opps = await self._compose_all(org_id)
        decisions = await self._load_decisions(org_id)
        out: list[dict[str, Any]] = []
        for opp in opps:
            dec = decisions.get(opp["id"])
            if not include_ignored and dec == "ignore":
                continue
            if dec:
                opp = {**opp, "user_decision": dec}
            out.append(opp)
            if len(out) >= limit:
                break
        return out

    async def summary(self, org_id: uuid.UUID) -> dict[str, Any]:
        opps = await self.list_opportunities(org_id, limit=100)
        plan = await PublishingPlanService(self._session).get_plan(org_id)
        trends = await list_org_trends(self._session, org_id, limit=50)
        article_count = await self._count_articles(org_id)
        scheduled = 0
        needs_review = len(plan.get("review_queue") or [])
        # Count scheduled from to-post style drafts
        rows = (
            await self._session.execute(
                select(Draft).where(
                    Draft.organization_id == org_id,
                    Draft.status.in_(
                        (DraftStatus.APPROVED, DraftStatus.PUBLISHED, "approved", "published")
                    ),
                ).limit(200)
            )
        ).scalars().all()
        for d in rows:
            meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
            if meta.get("scheduled_for"):
                scheduled += 1

        high = sum(1 for o in opps if o.get("priority") == "high")
        recommended_today = sum(
            1
            for o in opps
            if o.get("timeline_bucket") == "today" and o.get("recommendation", {}).get("should_generate")
        )
        avg = 0
        if opps:
            avg = int(round(sum(o["opportunity_score"] for o in opps) / len(opps)))

        return {
            "articles_analysed": article_count,
            "opportunities": len(opps),
            "trends": len(trends),
            "high_priority": high,
            "recommended_today": recommended_today,
            "already_scheduled": scheduled,
            "needs_review": needs_review,
            "average_opportunity_score": avg,
            "label": "estimated",
            "plan_health": {
                "target": plan.get("target"),
                "counts": plan.get("counts"),
                "gaps": plan.get("gaps"),
                "window": plan.get("window"),
                "days_left": plan.get("days_left"),
                "slots": plan.get("slots") or [],
                "needs_capture": plan.get("needs_capture") or {},
            },
            "review_queue": plan.get("review_queue") or [],
        }

    async def strategist_briefing(self, org_id: uuid.UUID) -> dict[str, Any]:
        from app.modules.content.application.strategist_briefing import build_strategist_briefing

        opps = await self.list_opportunities(org_id, limit=40)
        summary = await self.summary(org_id)
        trends = await list_org_trends(self._session, org_id, limit=15)
        brand = await self._load_brand(org_id)
        memory = await self._memory_hints(org_id, summary.get("plan_health") or {})
        return build_strategist_briefing(
            opportunities=opps,
            summary=summary,
            trends=trends,
            brand=brand,
            memory=memory,
            config=self._cfg,
        )

    async def set_decision(
        self,
        org_id: uuid.UUID,
        opportunity_id: str,
        action: str,
    ) -> dict[str, Any]:
        if action not in ("save", "ignore", "clear"):
            raise ValueError("action must be save, ignore, or clear")
        kit = await self._load_brand_row(org_id)
        if kit is None:
            # Create minimal preference store on a synthetic path via BrandKit if missing
            kit = BrandKit(
                organization_id=org_id,
                name="Default",
                extra_settings={},
            )
            self._session.add(kit)
            await self._session.flush()
        extra = dict(kit.extra_settings or {})
        decisions = dict(extra.get("opportunity_decisions") or {})
        if action == "clear":
            decisions.pop(opportunity_id, None)
        else:
            decisions[opportunity_id] = action
        extra["opportunity_decisions"] = decisions
        kit.extra_settings = extra
        await self._session.flush()
        return {"opportunity_id": opportunity_id, "action": action if action != "clear" else None}

    async def _compose_all(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        cfg = self._cfg
        weights = cfg.get("weights") or {}
        angle_map = {str(k): str(v) for k, v in (cfg.get("angle_map") or {}).items()}
        soft_cap = int(cfg.get("competition_soft_cap") or 3)

        # Load detector tag weights from news config if present
        tag_weights = self._load_tag_weights()
        brand_topics: list[str] = []
        try:
            from app.modules.brand_intelligence.application.news_policy_service import (
                BrandNewsPolicyService,
                topic_overlap_score,
            )

            brand_policy = await BrandNewsPolicyService(self._session).get_for_org(org_id)
            brand_topics = list(brand_policy.topics) + list(brand_policy.weight_up[:20])
        except Exception:  # noqa: BLE001
            topic_overlap_score = None  # type: ignore[assignment]

        articles = await self._load_candidate_articles(org_id)
        if not articles:
            return []

        source_ids = {a.source_id for a in articles}
        sources = (
            await self._session.execute(
                select(NewsSource).where(NewsSource.id.in_(list(source_ids)))
            )
        ).scalars().all()
        source_by_id = {s.id: s for s in sources}

        scores = (
            await self._session.execute(
                select(RelevanceScore).where(
                    RelevanceScore.organization_id == org_id,
                    RelevanceScore.article_id.in_([a.id for a in articles]),
                )
            )
        ).scalars().all()
        # Best score per article
        best_score: dict[uuid.UUID, RelevanceScore] = {}
        for s in scores:
            prev = best_score.get(s.article_id)
            if prev is None or s.score > prev.score:
                best_score[s.article_id] = s

        drafts = (
            await self._session.execute(
                select(Draft)
                .where(
                    Draft.organization_id == org_id,
                    Draft.article_id.is_not(None),
                )
                .order_by(Draft.created_at.desc())
                .limit(300)
            )
        ).scalars().all()
        drafts_by_article: dict[uuid.UUID, Draft] = {}
        for d in drafts:
            if d.article_id and d.article_id not in drafts_by_article:
                drafts_by_article[d.article_id] = d

        approved_drafts = [
            d
            for d in drafts
            if (d.status or "").lower()
            in (DraftStatus.APPROVED, DraftStatus.PUBLISHED, "approved", "published")
        ]

        trends = await list_org_trends(self._session, org_id, limit=30)
        trend_keys = {str(t.get("topic_key") or "").lower(): t for t in trends}

        # Group articles into opportunities (title similarity clusters)
        groups = self._group_articles(articles)

        now = datetime.now(timezone.utc)
        plan = await PublishingPlanService(self._session).get_plan(org_id)
        edu_gap = int((plan.get("gaps") or {}).get("educational") or 0)

        opportunities: list[dict[str, Any]] = []
        for group in groups:
            article_ids = [a.id for a in group]
            lead = max(
                group,
                key=lambda a: (best_score.get(a.id).score if best_score.get(a.id) else 0),
            )
            rel_row = best_score.get(lead.id)
            relevance = int(rel_row.score) if rel_row else None
            audience = rel_row.audience if rel_row else None
            angle_text = (rel_row.angle if rel_row else None) or ""
            reason = (rel_row.reason if rel_row else None) or ""

            tags: list[str] = []
            for a in group:
                for t in extract_opportunity_tags(a):
                    if t not in tags:
                        tags.append(t)

            # Trend match
            trend_score = 0.35
            title_tokens = tokenize(lead.title)
            for key, trow in trend_keys.items():
                key_tokens = tokenize(key.replace("-", " ").replace("_", " "))
                if key_tokens & title_tokens:
                    growth = trow.get("growth") or trow.get("momentum") or 0
                    try:
                        trend_score = max(trend_score, float(growth) if float(growth) <= 1 else float(growth) / 100)
                    except (TypeError, ValueError):
                        trend_score = max(trend_score, 0.6)
                    break

            pub_at = lead.published_at or lead.created_at
            age_hours = None
            if pub_at:
                if pub_at.tzinfo is None:
                    pub_at = pub_at.replace(tzinfo=timezone.utc)
                age_hours = (now - pub_at).total_seconds() / 3600.0

            # Competition: similar approved hooks
            competition_count = 0
            for d in approved_drafts:
                if title_similarity(lead.title, d.hook or "") >= 0.35:
                    competition_count += 1

            overlap = 0.0
            if brand_topics and topic_overlap_score is not None:
                overlap = topic_overlap_score(
                    f"{lead.title} {lead.summary or ''} {audience or ''}",
                    brand_topics,
                )
            confidence = compute_confidence_factors(
                relevance=relevance,
                tags=tags,
                tag_weights=tag_weights,
                trend_score=trend_score,
                age_hours=age_hours,
                audience=audience,
                competition_count=competition_count,
                soft_cap=soft_cap,
                weights=weights,
                brand_topic_overlap=overlap,
            )

            primary_angle, alt_angles = map_angles(tags, angle_map)
            if angle_text and primary_angle == "Educational":
                # Prefer scorer angle as primary label hint
                primary_angle = "Educational"

            why_selected: list[str] = []
            if audience:
                why_selected.append(f"Audience: {audience}")
            if reason:
                why_selected.append(reason[:160])
            if tags:
                why_selected.append(f"Opportunity signals: {', '.join(tags[:3])}")
            if confidence["trend"] >= 70:
                why_selected.append("Trending topic")
            if not why_selected:
                why_selected.append("Matches screened news relevance")

            bucket, timing_advice = timeline_bucket_for(
                freshness=confidence["freshness"],
                trend=confidence["trend"],
                age_hours=age_hours,
            )

            # Publisher breakdown
            pub_counts: dict[str, int] = {}
            for a in group:
                name = publisher_from_article(a, source_by_id.get(a.source_id))
                pub_counts[name] = pub_counts.get(name, 0) + 1
            by_publisher = [
                {"name": n, "count": c}
                for n, c in sorted(pub_counts.items(), key=lambda x: -x[1])
            ]

            # Similar posts
            similar: list[dict[str, Any]] = []
            for d in approved_drafts:
                sim = title_similarity(lead.title, f"{d.hook or ''} {d.content_type or ''}")
                if sim >= 0.25:
                    similar.append(
                        {
                            "id": str(d.id),
                            "title": d.hook or "Untitled post",
                            "content_type": d.content_type,
                            "impressions": None,
                            "note": "Estimated similarity — no LinkedIn impressions yet",
                        }
                    )
                if len(similar) >= 3:
                    break

            # Duplicate detection vs recent drafts
            duplicate = {
                "already_covered": False,
                "covered_at": None,
                "peer_opportunity_id": None,
                "peer_draft_id": None,
            }
            for d in approved_drafts[:50]:
                if title_similarity(lead.title, d.hook or "") >= 0.5:
                    duplicate = {
                        "already_covered": True,
                        "covered_at": d.created_at.date().isoformat() if d.created_at else None,
                        "peer_opportunity_id": None,
                        "peer_draft_id": str(d.id),
                    }
                    break

            stage = lifecycle_for_article(lead.id, drafts_by_article)
            if stage == "recommended" and relevance is not None:
                stage = "scored" if confidence["composite"] < 70 else "recommended"

            score = confidence["composite"]
            priority = "high" if score >= 85 else "medium" if score >= 65 else "low"

            audiences = []
            if audience:
                audiences.append(str(audience))
            sector = rel_row.sector if rel_row else None
            if sector and sector not in audiences:
                audiences.append(str(sector))

            opp_id = opportunity_id_for(article_ids)
            recommendation = build_recommendation(confidence, why_selected)

            opportunities.append(
                {
                    "id": opp_id,
                    "title": self._cluster_title(group),
                    "kind": "cluster" if len(group) > 1 else "article",
                    "timeline_bucket": bucket,
                    "timing_advice": timing_advice,
                    "opportunity_score": score,
                    "confidence": confidence,
                    "recommendation": recommendation,
                    "sources": {
                        "by_publisher": by_publisher,
                        "article_ids": [str(i) for i in article_ids],
                        "source_count": len(group),
                    },
                    "why_selected": why_selected[:6],
                    "audiences": audiences or ["general"],
                    "primary_angle": primary_angle,
                    "alt_angles": alt_angles,
                    "lifecycle_stage": stage,
                    "duplicate": duplicate,
                    "similar_posts": similar,
                    "similar_posts_note": (
                        None
                        if similar
                        else "No historical posts yet — estimates only"
                    ),
                    "fortnight_fit": {
                        "content_type": "educational",
                        "gap_remaining": edu_gap,
                    },
                    "priority": priority,
                    "primary_article_id": str(lead.id),
                    "estimates_label": "estimated",
                }
            )

        opportunities.sort(key=lambda o: (-o["opportunity_score"], o["title"]))
        return opportunities

    def _group_articles(self, articles: list[Article]) -> list[list[Article]]:
        remaining = list(articles)
        groups: list[list[Article]] = []
        while remaining:
            lead = remaining.pop(0)
            cluster = [lead]
            kept: list[Article] = []
            for other in remaining:
                if title_similarity(lead.title, other.title) >= 0.4:
                    cluster.append(other)
                else:
                    kept.append(other)
            remaining = kept
            groups.append(cluster)
        return groups

    def _cluster_title(self, group: list[Article]) -> str:
        if len(group) == 1:
            return group[0].title
        # Shared significant tokens
        shared: set[str] | None = None
        for a in group:
            tokens = tokenize(a.title)
            shared = tokens if shared is None else shared & tokens
        if shared and len(shared) >= 2:
            words = sorted(shared, key=lambda w: (-len(w), w))[:4]
            return " ".join(w.title() for w in words)
        return f"{group[0].title.split(':')[0].strip()} ({len(group)} sources)"

    async def _load_candidate_articles(self, org_id: uuid.UUID) -> list[Article]:
        statuses = (
            ArticleStatus.RELEVANT,
            ArticleStatus.SCORED,
            "relevant",
            "scored",
        )
        return list(
            (
                await self._session.execute(
                    select(Article)
                    .where(
                        Article.organization_id == org_id,
                        Article.status.in_(statuses),
                    )
                    .order_by(Article.created_at.desc())
                    .limit(80)
                )
            ).scalars().all()
        )

    async def _count_articles(self, org_id: uuid.UUID) -> int:
        start, end = fortnight_window()
        start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        result = await self._session.execute(
            select(func.count())
            .select_from(Article)
            .where(
                Article.organization_id == org_id,
                Article.created_at >= start_dt,
            )
        )
        return int(result.scalar_one() or 0)

    async def _load_brand(self, org_id: uuid.UUID) -> dict[str, Any]:
        row = await self._load_brand_row(org_id)
        if row is None:
            return {}
        extra = row.extra_settings if isinstance(row.extra_settings, dict) else {}
        goal = extra.get("strategic_goal") or row.description or row.services_line
        return {
            "name": row.name,
            "strategic_goal": goal,
            "services_line": row.services_line,
            "description": row.description,
            "extra_settings": extra,
        }

    async def _load_brand_row(self, org_id: uuid.UUID) -> BrandKit | None:
        return (
            await self._session.execute(
                select(BrandKit).where(BrandKit.organization_id == org_id).limit(1)
            )
        ).scalar_one_or_none()

    async def _load_decisions(self, org_id: uuid.UUID) -> dict[str, str]:
        brand = await self._load_brand(org_id)
        extra = brand.get("extra_settings") or {}
        raw = extra.get("opportunity_decisions") or {}
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

    async def _memory_hints(self, org_id: uuid.UUID, plan_health: dict) -> list[str]:
        hints: list[str] = []
        gaps = plan_health.get("gaps") or {}
        if int(gaps.get("success_story") or 0) > 0:
            hints.append(
                f"Success stories are underrepresented this fortnight "
                f"({gaps.get('success_story')} still needed)."
            )
        if int(gaps.get("personal_achievement") or 0) > 0:
            hints.append(
                f"Personal achievements gap: {gaps.get('personal_achievement')} still needed."
            )
        if int(gaps.get("educational") or 0) > 0:
            hints.append(
                f"Educational mix still needs {gaps.get('educational')} more post(s)."
            )

        gap_days = int(self._cfg.get("memory_gap_days") or 14)
        cutoff = datetime.now(timezone.utc) - timedelta(days=gap_days)
        recent = (
            await self._session.execute(
                select(Draft)
                .where(
                    Draft.organization_id == org_id,
                    Draft.status.in_(
                        (DraftStatus.APPROVED, DraftStatus.PUBLISHED, "approved", "published")
                    ),
                    Draft.created_at >= cutoff - timedelta(days=60),
                )
                .order_by(Draft.created_at.desc())
                .limit(50)
            )
        ).scalars().all()

        topic_words = ("zero trust", "identity", "healthcare", "compliance", "microsoft", "azure")
        hooks = " ".join((d.hook or "").lower() for d in recent if d.created_at and d.created_at >= cutoff)
        for topic in topic_words:
            if topic not in hooks:
                # Check if ever posted
                ever = any(topic in (d.hook or "").lower() for d in recent)
                if ever:
                    hints.append(f"You haven't posted about {topic.title()} for {gap_days}+ days.")
                break

        return hints[:4]

    def _load_tag_weights(self) -> dict[str, float]:
        path = Path(__file__).resolve().parents[4] / "configs" / "news" / "opportunities.yaml"
        if not path.is_file():
            return {}
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        w = raw.get("weights") or {}
        return {str(k): float(v) for k, v in w.items()}
