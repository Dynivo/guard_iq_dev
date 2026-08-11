"""Story Timeline — cluster updates into ordered story arcs."""

from __future__ import annotations

from datetime import datetime, timezone

from app.modules.news.domain.models import (
    ArticleCluster,
    CanonicalArticle,
    StoryTimeline,
)


class DefaultStoryTimelineBuilder:
    def build(
        self,
        clusters: list[ArticleCluster],
        articles: list[CanonicalArticle],
        *,
        events_by_url: dict[str, list[str]] | None = None,
    ) -> list[StoryTimeline]:
        by_url = {(a.canonical_url or a.url): a for a in articles}
        events_by_url = events_by_url or {}
        timelines: list[StoryTimeline] = []
        for cluster in clusters:
            members = [
                by_url[u] for u in cluster.article_urls if u in by_url
            ]
            members.sort(
                key=lambda a: a.published_at
                or a.updated_at
                or datetime.min.replace(tzinfo=timezone.utc)
            )
            urls = tuple(m.canonical_url or m.url for m in members)
            evts: list[str] = []
            for u in urls:
                evts.extend(events_by_url.get(u, []))
            started = members[0].published_at if members else None
            updated = members[-1].published_at if members else None
            timelines.append(
                StoryTimeline(
                    story_id=cluster.cluster_id,
                    label=cluster.label,
                    article_urls=urls,
                    events=tuple(dict.fromkeys(evts)),
                    started_at=started,
                    updated_at=updated,
                    cohesion=cluster.cohesion,
                )
            )
        return timelines
