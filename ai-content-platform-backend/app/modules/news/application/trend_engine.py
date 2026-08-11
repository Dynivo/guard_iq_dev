"""Trend Engine — topic growth/momentum/velocity/popularity (+ predicted stub)."""

from __future__ import annotations

from collections import defaultdict

from app.modules.news.domain.models import CanonicalArticle, TopicSignals, TrendMetrics


class DefaultTrendEngine:
    def __init__(self) -> None:
        self._history: dict[str, list[int]] = defaultdict(list)
        self._latest: dict[str, TrendMetrics] = {}

    def observe_batch(
        self, articles: list[CanonicalArticle], topics: list[TopicSignals]
    ) -> list[TrendMetrics]:
        counts: dict[str, int] = defaultdict(int)
        for art, topic in zip(articles, topics, strict=False):
            keys = _topic_keys(art, topic)
            for key in keys:
                counts[key] += 1

        results: list[TrendMetrics] = []
        for key, count in counts.items():
            hist = self._history[key]
            prev = hist[-1] if hist else 0
            hist.append(count)
            if len(hist) > 12:
                hist.pop(0)
            growth = (count - prev) / max(1, prev) if prev else float(count > 0)
            velocity = count - prev
            momentum = sum(hist[-3:]) / max(1, min(3, len(hist)))
            popularity = min(1.0, count / max(1, sum(counts.values())))
            # Future prediction stub: dampened momentum
            predicted = min(1.0, max(0.0, 0.5 * momentum / max(1.0, max(hist)) + 0.3 * growth))
            metrics = TrendMetrics(
                topic_key=key,
                growth=round(growth, 4),
                momentum=round(momentum, 4),
                velocity=float(velocity),
                popularity=round(popularity, 4),
                predicted_trend=round(predicted, 4),
                article_count=count,
            )
            self._latest[key] = metrics
            results.append(metrics)
        return results

    def get(self, topic_key: str) -> TrendMetrics | None:
        return self._latest.get(topic_key)

    def snapshot(self) -> dict[str, dict]:
        return {k: v.to_dict() for k, v in self._latest.items()}


def _topic_keys(article: CanonicalArticle, topic: TopicSignals) -> list[str]:
    keys: list[str] = []
    for part in (topic.industry, topic.framework, topic.threat, topic.category, article.category):
        if part:
            keys.append(part.lower())
    if not keys:
        keys.append("general")
    return list(dict.fromkeys(keys))
