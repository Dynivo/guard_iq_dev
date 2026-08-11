"""Entity extraction — companies, CVEs, frameworks, etc. (deterministic)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.modules.news.domain.models import CanonicalArticle, ExtractedEntities, TopicSignals

_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

_DEFAULT_TECH = (
    "azure",
    "aws",
    "microsoft",
    "google",
    "kubernetes",
    "endpoint",
    "identity",
    "firewall",
    "cloud",
)
_DEFAULT_FRAMEWORKS = ("dspt", "nis2", "iso27001", "soc2", "gdpr", "hipaa", "pci-dss")
_DEFAULT_REGS = ("gdpr", "nis2", "ccpa", "dora")
_DEFAULT_INDUSTRIES = ("healthcare", "finance", "government", "education", "retail")
_DEFAULT_COUNTRIES = {
    "uk": "UK",
    "united kingdom": "UK",
    "us": "US",
    "united states": "US",
    "eu": "EU",
    "europe": "EU",
}
_DEFAULT_COMPANIES = (
    "microsoft",
    "google",
    "amazon",
    "apple",
    "ibm",
    "cisco",
    "palo alto",
    "crowdstrike",
)


@dataclass
class EntityRecord:
    entity_type: str
    value: str
    confidence: float = 0.8
    article_url: str = ""
    organization_id: str = ""
    metadata: dict = field(default_factory=dict)


class InMemoryEntityStore:
    def __init__(self) -> None:
        self._rows: list[EntityRecord] = []

    def save(self, record: EntityRecord) -> None:
        self._rows.append(record)

    def list_for_url(self, article_url: str) -> list[EntityRecord]:
        return [r for r in self._rows if r.article_url == article_url]

    def all(self) -> list[EntityRecord]:
        return list(self._rows)


class DefaultEntityExtractor:
    def __init__(
        self,
        *,
        technologies: tuple[str, ...] | None = None,
        frameworks: tuple[str, ...] | None = None,
        regulations: tuple[str, ...] | None = None,
        industries: tuple[str, ...] | None = None,
        companies: tuple[str, ...] | None = None,
        store: InMemoryEntityStore | None = None,
    ) -> None:
        self._tech = technologies or _DEFAULT_TECH
        self._frameworks = frameworks or _DEFAULT_FRAMEWORKS
        self._regs = regulations or _DEFAULT_REGS
        self._industries = industries or _DEFAULT_INDUSTRIES
        self._companies = companies or _DEFAULT_COMPANIES
        self._store = store or InMemoryEntityStore()

    @property
    def store(self) -> InMemoryEntityStore:
        return self._store

    def extract(
        self, article: CanonicalArticle, *, topic: TopicSignals | None = None
    ) -> ExtractedEntities:
        text = f"{article.title} {article.summary} {article.body_text}".lower()
        cves = tuple(sorted({m.group(0).upper() for m in _CVE.finditer(text)}))
        techs = _matches(text, self._tech)
        frameworks = _matches(text, self._frameworks)
        regs = _matches(text, self._regs)
        industries = _matches(text, self._industries)
        companies = _matches(text, self._companies)
        countries: list[str] = []
        for needle, code in _DEFAULT_COUNTRIES.items():
            if needle in text and code not in countries:
                countries.append(code)
        if topic:
            if topic.framework and topic.framework not in frameworks:
                frameworks = frameworks + (topic.framework,)
            if topic.industry and topic.industry not in industries:
                industries = industries + (topic.industry,)
            if topic.technology and topic.technology not in techs:
                techs = techs + (topic.technology,)
            if topic.country and topic.country not in countries:
                countries.append(topic.country)
            if topic.company and topic.company not in companies:
                companies = companies + (topic.company,)

        entities = ExtractedEntities(
            companies=tuple(companies),
            products=(),
            technologies=tuple(techs),
            cves=cves,
            countries=tuple(countries),
            industries=tuple(industries),
            regulations=tuple(regs),
            frameworks=tuple(frameworks),
        )
        url = article.canonical_url or article.url
        org = str(article.organization_id or "")
        for etype, value in entities.flat_records():
            self._store.save(
                EntityRecord(
                    entity_type=etype,
                    value=value,
                    article_url=url,
                    organization_id=org,
                    confidence=0.85 if etype == "cve" else 0.7,
                )
            )
        return entities


def _matches(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    found: list[str] = []
    for term in terms:
        if re.search(rf"\b{re.escape(term)}\b", text):
            found.append(term)
    return tuple(found)
