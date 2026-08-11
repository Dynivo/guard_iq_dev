"""Cluster Engine — topic/title similarity + time window + source diversity."""

from __future__ import annotations

import uuid
from datetime import timedelta
from difflib import SequenceMatcher

from app.modules.news.domain.models import ArticleCluster, CanonicalArticle, NewsPolicy


def _title_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class DefaultClusterEngine:
    def cluster(
        self, articles: list[CanonicalArticle], *, policy: NewsPolicy
    ) -> list[ArticleCluster]:
        if not articles:
            return []

        remaining = list(articles)
        clusters: list[ArticleCluster] = []
        threshold = policy.cluster_similarity_threshold
        window = timedelta(hours=policy.cluster_time_window_hours)

        while remaining:
            seed = remaining.pop(0)
            members = [seed]
            sources = {seed.source}
            i = 0
            while i < len(remaining) and len(members) < policy.max_cluster_size:
                cand = remaining[i]
                time_ok = True
                if seed.published_at and cand.published_at:
                    time_ok = abs(seed.published_at - cand.published_at) <= window
                sim = _title_sim(seed.title, cand.title)
                # Prefer source diversity: allow same-source only if very similar
                same_source = cand.source and cand.source in sources
                if time_ok and sim >= threshold and (not same_source or sim >= 0.9):
                    members.append(cand)
                    sources.add(cand.source)
                    remaining.pop(i)
                    continue
                i += 1

            cohesion = 1.0
            if len(members) > 1:
                pairs = [
                    _title_sim(members[0].title, m.title) for m in members[1:]
                ]
                cohesion = sum(pairs) / len(pairs) if pairs else 1.0

            clusters.append(
                ArticleCluster(
                    cluster_id=str(uuid.uuid4()),
                    label=members[0].title[:200],
                    article_urls=tuple(m.canonical_url or m.url for m in members),
                    cohesion=cohesion,
                    summary=members[0].summary[:500],
                    metadata={"size": len(members), "sources": sorted(sources)},
                )
            )
        return clusters


class DefaultClusterAnalyzer:
    def analyze(self, clusters: list[ArticleCluster]) -> dict:
        if not clusters:
            return {"count": 0, "avg_cohesion": 0.0, "avg_size": 0.0}
        sizes = [len(c.article_urls) for c in clusters]
        return {
            "count": len(clusters),
            "avg_cohesion": sum(c.cohesion for c in clusters) / len(clusters),
            "avg_size": sum(sizes) / len(sizes),
            "multi_article_clusters": sum(1 for s in sizes if s > 1),
        }
