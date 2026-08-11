"""Event detection from article text + topic signals (YAML-driven patterns)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.modules.news.domain.models import (
    CanonicalArticle,
    DetectedEvent,
    NewsEventType,
    TopicSignals,
)

_DEFAULT_DIR = Path(__file__).resolve().parents[4] / "configs" / "news"

_DEFAULT_PATTERNS: dict[str, tuple[str, ...]] = {
    NewsEventType.BREACH.value: ("data breach", "breached", "exposed records"),
    NewsEventType.ACQUISITION.value: ("acquires", "acquisition", "merger"),
    NewsEventType.PRODUCT_LAUNCH.value: ("launches", "announces", "introduces"),
    NewsEventType.PATCH_RELEASE.value: ("patch", "patches", "security update"),
    NewsEventType.VULNERABILITY.value: ("vulnerability", "cve-", "zero-day", "exploit"),
    NewsEventType.FUNDING.value: ("raises", "funding", "series a", "series b"),
    NewsEventType.REGULATION.value: ("regulation", "regulatory", "legislation"),
    NewsEventType.COMPLIANCE.value: ("compliance", "dspt", "nis2", "audit"),
    NewsEventType.INCIDENT.value: ("incident", "outage", "disruption"),
}


@dataclass
class EventRecord:
    event_type: str
    confidence: float = 0.0
    evidence: str = ""
    article_url: str = ""
    organization_id: str = ""
    metadata: dict = field(default_factory=dict)


class InMemoryEventStore:
    def __init__(self) -> None:
        self._rows: list[EventRecord] = []

    def save(self, record: EventRecord) -> None:
        self._rows.append(record)

    def list_for_url(self, article_url: str) -> list[EventRecord]:
        return [r for r in self._rows if r.article_url == article_url]

    def all(self) -> list[EventRecord]:
        return list(self._rows)


class DefaultEventDetector:
    def __init__(
        self,
        config_dir: Path | None = None,
        *,
        store: InMemoryEventStore | None = None,
    ) -> None:
        self._patterns = dict(_DEFAULT_PATTERNS)
        self._store = store or InMemoryEventStore()
        path = (config_dir or _DEFAULT_DIR) / "events.yaml"
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                for key, vals in (raw.get("patterns") or {}).items():
                    if isinstance(vals, list):
                        self._patterns[str(key)] = tuple(str(v).lower() for v in vals)

    @property
    def store(self) -> InMemoryEventStore:
        return self._store

    def detect(
        self, article: CanonicalArticle, *, topic: TopicSignals | None = None
    ) -> list[DetectedEvent]:
        text = f"{article.title} {article.summary} {article.body_text}".lower()
        events: list[DetectedEvent] = []
        for etype, needles in self._patterns.items():
            hits = [n for n in needles if n in text]
            if not hits:
                continue
            conf = min(1.0, 0.45 + 0.15 * len(hits))
            events.append(
                DetectedEvent(
                    event_type=etype,
                    confidence=conf,
                    evidence=hits[0],
                )
            )
        if topic and topic.threat and not any(
            e.event_type == NewsEventType.VULNERABILITY.value for e in events
        ):
            if topic.threat in {
                "ransomware",
                "phishing",
                "malware",
                "breach",
                "vulnerability",
            }:
                events.append(
                    DetectedEvent(
                        event_type=NewsEventType.INCIDENT.value
                        if topic.threat != "vulnerability"
                        else NewsEventType.VULNERABILITY.value,
                        confidence=0.55,
                        evidence=topic.threat,
                    )
                )
        url = article.canonical_url or article.url
        org = str(article.organization_id or "")
        for ev in events:
            self._store.save(
                EventRecord(
                    event_type=ev.event_type,
                    confidence=ev.confidence,
                    evidence=ev.evidence,
                    article_url=url,
                    organization_id=org,
                )
            )
        return events
