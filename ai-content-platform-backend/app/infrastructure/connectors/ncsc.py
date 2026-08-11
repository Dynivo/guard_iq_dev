"""NCSC (UK National Cyber Security Centre) advisory connector.

Wraps the RSS connector with the NCSC feed URL as the default.
Config can override `feed_url` if the feed location changes.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.infrastructure.connectors.rss import RSSConnector
from app.modules.news.domain.ports import NormalizedArticle

logger = get_logger(__name__)

_NCSC_DEFAULT_FEED = (
    "https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml"
)


class NCSCConnector(RSSConnector):
    """NCSC advisory feed — inherits RSS parsing, injects default URL."""

    connector_type = "ncsc"

    async def fetch(self, config: dict) -> list[NormalizedArticle]:
        effective_config = {**config}
        if "feed_url" not in effective_config:
            effective_config["feed_url"] = _NCSC_DEFAULT_FEED
        articles = await super().fetch(effective_config)
        logger.info("NCSC connector returned %d articles", len(articles))
        return articles
