"""Brand source connectors producing Canonical Brand Objects only."""

from __future__ import annotations

import hashlib
import re
import uuid
from html import unescape
from typing import Any
from urllib.parse import urlparse

import httpx

from app.modules.brand_intelligence.application.engines.core import fingerprint_text
from app.modules.brand_intelligence.domain.models import (
    CanonicalBrandObject,
    CboObjectType,
    CboSourceType,
)

from app.modules.brand_intelligence.infrastructure.connectors.linkedin_connector import (
    LinkedInConnector,
)



def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class WebsiteConnector:
    source_type = "website"

    async def fetch(self, config: dict[str, Any], session_state: bytes | None = None) -> list[CanonicalBrandObject]:
        _ = session_state
        org_id = uuid.UUID(str(config["organization_id"]))
        profile_id = uuid.UUID(str(config["brand_profile_id"]))
        import_id = uuid.UUID(str(config["import_id"])) if config.get("import_id") else None
        seed = str(config.get("website_url") or "").strip()
        max_pages = int(config.get("max_pages") or 8)
        if not seed:
            return []

        crawler = SimpleCrawler()
        pages = await crawler.crawl(seed, max_pages=max_pages)
        objects: list[CanonicalBrandObject] = []
        for page in pages:
            url = page["url"]
            title = page.get("title") or url
            body = page.get("text") or ""
            objects.append(
                CanonicalBrandObject(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    brand_profile_id=profile_id,
                    import_id=import_id,
                    object_type=CboObjectType.PAGE,
                    source_type=CboSourceType.WEBSITE,
                    external_id=url,
                    canonical_url=url,
                    fingerprint=fingerprint_text("web", url, body[:2000]),
                    title=title,
                    body_text=body[:30000],
                    html_sanitized=page.get("html_sanitized"),
                    metadata_json={"section_guess": page.get("section_guess")},
                )
            )
        return objects


class SimpleCrawler:
    async def crawl(self, seed_url: str, max_pages: int = 20) -> list[dict[str, Any]]:
        parsed = urlparse(seed_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        seen: set[str] = set()
        queue = [seed_url]
        out: list[dict[str, Any]] = []
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            while queue and len(out) < max_pages:
                url = queue.pop(0)
                if url in seen:
                    continue
                seen.add(url)
                try:
                    resp = await client.get(url, headers={"User-Agent": "BrandIntelligenceBot/1.0"})
                    if resp.status_code >= 400 or "text/html" not in resp.headers.get("content-type", ""):
                        continue
                    html = resp.text
                    text = _strip_html(html)
                    title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
                    title = _strip_html(title_m.group(1)) if title_m else url
                    section = "about" if any(k in url.lower() for k in ("about", "mission", "company")) else "page"
                    if "service" in url.lower():
                        section = "services"
                    if "case" in url.lower() or "blog" in url.lower():
                        section = "case_studies" if "case" in url.lower() else "blogs"
                    out.append(
                        {
                            "url": url,
                            "title": title,
                            "text": text[:50000],
                            "html_sanitized": text[:50000],
                            "section_guess": section,
                        }
                    )
                    for href in re.findall(r'href=["\'](.*?)["\']', html, flags=re.I):
                        if href.startswith("/"):
                            href = origin + href
                        if href.startswith(origin) and href not in seen and len(queue) < max_pages * 2:
                            queue.append(href.split("#")[0])
                except Exception:
                    continue
        return out


class UploadConnector:
    source_type = "upload"

    async def fetch(self, config: dict[str, Any], session_state: bytes | None = None) -> list[CanonicalBrandObject]:
        _ = session_state
        org_id = uuid.UUID(str(config["organization_id"]))
        profile_id = uuid.UUID(str(config["brand_profile_id"]))
        import_id = uuid.UUID(str(config["import_id"])) if config.get("import_id") else None
        artifacts = config.get("artifacts") or []
        objects: list[CanonicalBrandObject] = []
        for art in artifacts:
            if not isinstance(art, dict):
                continue
            kind = str(art.get("kind") or "document")
            text = str(art.get("extracted_text") or art.get("filename") or "")
            storage_key = art.get("storage_key")
            obj_type = {
                "logo": CboObjectType.MEDIA,
                "guideline": CboObjectType.GUIDELINE,
                "image": CboObjectType.MEDIA,
                "video": CboObjectType.MEDIA,
                "pdf": CboObjectType.DOCUMENT,
                "document": CboObjectType.DOCUMENT,
                "email": CboObjectType.EMAIL,
                "post": CboObjectType.POST,
            }.get(kind, CboObjectType.OTHER)
            objects.append(
                CanonicalBrandObject(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    brand_profile_id=profile_id,
                    import_id=import_id,
                    object_type=obj_type,
                    source_type=CboSourceType.EMAIL if kind == "email" else CboSourceType.UPLOAD,
                    fingerprint=fingerprint_text(kind, str(storage_key), text[:500]),
                    title=str(art.get("filename") or kind),
                    body_text=text[:50000] if text else None,
                    media_refs=[{"storage_key": storage_key, "kind": kind}] if storage_key else [],
                    metadata_json={"kind": kind},
                )
            )
        return objects


class EmailConnector(UploadConnector):
    source_type = "email"


class ConnectorRegistry:
    def __init__(self) -> None:
        self._map: dict[str, Any] = {
            "linkedin": LinkedInConnector(),
            "website": WebsiteConnector(),
            "upload": UploadConnector(),
            "email": EmailConnector(),
            # Future stubs — same UploadConnector shape, not implemented scrapers
            "youtube": UploadConnector(),
            "medium": UploadConnector(),
            "substack": UploadConnector(),
            "wordpress": UploadConnector(),
            "ghost": UploadConnector(),
            "hubspot": UploadConnector(),
            "rss": UploadConnector(),
        }

    def get(self, source_type: str) -> Any:
        if source_type not in self._map:
            raise KeyError(f"Unknown brand source connector: {source_type}")
        return self._map[source_type]
