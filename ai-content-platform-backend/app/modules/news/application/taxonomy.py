"""News taxonomy assigner — Industry → Topic → Subtopic → Framework → Tags."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.news.domain.models import (
    CanonicalArticle,
    ExtractedEntities,
    TaxonomyPath,
    TopicSignals,
)

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "news" / "taxonomy"


class YamlTaxonomyLoader:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (_DEFAULT_DIR / "default.yaml")
        self._tree: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                self._tree = raw.get("industries") or raw

    @property
    def tree(self) -> dict[str, Any]:
        return self._tree


class DefaultTaxonomyAssigner:
    def __init__(self, loader: YamlTaxonomyLoader | None = None) -> None:
        self._loader = loader or YamlTaxonomyLoader()

    def assign(
        self,
        article: CanonicalArticle,
        *,
        topic: TopicSignals,
        entities: ExtractedEntities | None = None,
    ) -> TaxonomyPath:
        tree = self._loader.tree
        industry = topic.industry or _first_key_match(article, tree) or "general"
        industry_node = tree.get(industry) if isinstance(tree.get(industry), dict) else {}
        topics = industry_node.get("topics") if isinstance(industry_node, dict) else {}
        if not isinstance(topics, dict):
            topics = {}
        topic_name = topic.category or topic.threat or _first_key_match(article, topics) or "general"
        topic_node = topics.get(topic_name) if isinstance(topics.get(topic_name), dict) else {}
        subtopics = topic_node.get("subtopics") if isinstance(topic_node, dict) else []
        subtopic = ""
        if isinstance(subtopics, list) and subtopics:
            text = f"{article.title} {article.summary}".lower()
            for s in subtopics:
                if str(s).lower() in text:
                    subtopic = str(s)
                    break
            if not subtopic:
                subtopic = str(subtopics[0])
        framework = topic.framework or (
            entities.frameworks[0] if entities and entities.frameworks else ""
        )
        tags = list(article.tags)
        if topic.threat and topic.threat not in tags:
            tags.append(topic.threat)
        if framework and framework not in tags:
            tags.append(framework)
        if entities:
            for cve in entities.cves[:3]:
                if cve not in tags:
                    tags.append(cve)
        return TaxonomyPath(
            industry=industry,
            topic=topic_name,
            subtopic=subtopic,
            framework=framework,
            tags=tuple(tags),
        )


def _first_key_match(article: CanonicalArticle, node: dict[str, Any]) -> str:
    text = f"{article.title} {article.summary} {article.body_text}".lower()
    for key in node.keys():
        if str(key).lower() in text:
            return str(key)
    return ""
