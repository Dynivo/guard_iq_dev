"""Topic Intelligence — deterministic enrichment from article + policy (no hardcoded product keywords)."""

from __future__ import annotations

import re

from app.modules.news.domain.models import CanonicalArticle, NewsPolicy, TopicSignals

# Configurable taxonomies live in policy YAML; defaults are structural labels only.
_DEFAULT_INDUSTRIES = ("healthcare", "finance", "government", "technology", "education")
_DEFAULT_FRAMEWORKS = ("dspt", "nis2", "iso27001", "soc2", "gdpr", "hipaa")
_DEFAULT_THREATS = ("ransomware", "phishing", "malware", "breach", "vulnerability", "zero-day")
_DEFAULT_TECH = ("cloud", "microsoft", "azure", "aws", "endpoint", "identity", "network")


class DefaultTopicIntelligence:
    def __init__(
        self,
        *,
        industries: tuple[str, ...] | None = None,
        frameworks: tuple[str, ...] | None = None,
        threats: tuple[str, ...] | None = None,
        technologies: tuple[str, ...] | None = None,
    ) -> None:
        self._industries = industries or _DEFAULT_INDUSTRIES
        self._frameworks = frameworks or _DEFAULT_FRAMEWORKS
        self._threats = threats or _DEFAULT_THREATS
        self._tech = technologies or _DEFAULT_TECH

    def analyze(self, article: CanonicalArticle, *, policy: NewsPolicy) -> TopicSignals:
        text = f"{article.title} {article.summary} {article.body_text}".lower()
        industry = _first_match(text, self._industries)
        framework = _first_match(text, self._frameworks)
        threat = _first_match(text, self._threats)
        technology = _first_match(text, self._tech)
        country = _guess_country(text)
        company = _guess_company(article)
        category = article.category or (threat and "threat") or (framework and "compliance") or "general"

        urgency = 0.3
        if threat:
            urgency += 0.35
        if "critical" in text or "emergency" in text:
            urgency += 0.2
        urgency = min(1.0, urgency)

        impact = 0.3 + (0.25 if industry else 0) + (0.2 if framework else 0)
        impact = min(1.0, impact)
        trend = 0.4 if threat or framework else 0.2
        confidence = 0.4 + 0.1 * sum(
            1 for x in (industry, framework, threat, technology) if x
        )
        confidence = min(1.0, confidence)

        return TopicSignals(
            category=category,
            industry=industry,
            threat=threat,
            technology=technology,
            country=country,
            company=company,
            framework=framework,
            urgency=urgency,
            trend=trend,
            business_impact=impact,
            confidence=confidence,
        )


def _first_match(text: str, terms: tuple[str, ...]) -> str:
    for term in terms:
        if re.search(rf"\b{re.escape(term)}\b", text):
            return term
    return ""


def _guess_country(text: str) -> str:
    mapping = {
        "united kingdom": "UK",
        " uk ": "UK",
        "britain": "UK",
        "united states": "US",
        " u.s.": "US",
        "europe": "EU",
    }
    padded = f" {text} "
    for needle, code in mapping.items():
        if needle in padded:
            return code
    return ""


def _guess_company(article: CanonicalArticle) -> str:
    # Prefer explicit metadata; avoid inventing vendors from free text alone
    meta = article.metadata or {}
    if meta.get("company"):
        return str(meta["company"])
    return ""
