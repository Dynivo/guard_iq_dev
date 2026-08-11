"""Derive news queries, in-scope terms, and relevance profile from Brand Memory."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.postgres.models.news import NewsSource
from app.modules.brand_intelligence.domain.news_policy import BrandNewsPolicy
from app.modules.brand_intelligence.infrastructure.postgres.repositories import (
    PgBrandMemoryRepository,
    PgBrandPersonaRepository,
    PgBrandProfileRepository,
    PgNeverSayRepository,
)
from app.modules.organization.infrastructure.brand_kit_repository import PgBrandKitRepository

logger = get_logger(__name__)

_CONFIG_PATH = (
    Path(__file__).resolve().parents[4] / "configs" / "brand_intelligence" / "news_policy.yaml"
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+./-]{1,40}", re.I)


@lru_cache(maxsize=1)
def load_news_policy_config() -> dict[str, Any]:
    if not _CONFIG_PATH.is_file():
        return {}
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def clear_news_policy_config_cache() -> None:
    load_news_policy_config.cache_clear()


def _labels(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                label = item.get("label") or item.get("name") or item.get("topic")
                if label:
                    out.append(str(label).strip())
    return out


def _uniq(items: list[str], *, limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
        if limit is not None and len(out) >= limit:
            break
    return out


def _quote_term(term: str) -> str:
    t = term.strip()
    if not t:
        return ""
    if " " in t or any(c in t for c in ("/", "-")):
        return f'"{t}"'
    return t


def build_search_query(terms: list[str], *, max_terms: int = 8) -> str:
    parts = [_quote_term(t) for t in _uniq(terms, limit=max_terms)]
    parts = [p for p in parts if p]
    return " OR ".join(parts)


def topic_overlap_score(text: str, topics: list[str]) -> float:
    """0–1 Jaccard-ish overlap between free text and brand topic tokens."""
    blob_tokens = set(_WORD_RE.findall((text or "").lower()))
    if not blob_tokens or not topics:
        return 0.0
    topic_tokens: set[str] = set()
    for t in topics:
        topic_tokens.update(_WORD_RE.findall(t.lower()))
    if not topic_tokens:
        return 0.0
    return len(blob_tokens & topic_tokens) / max(1, len(topic_tokens))


class BrandNewsPolicyService:
    """Build + apply BrandNewsPolicy for an organization."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._profiles = PgBrandProfileRepository(session)
        self._memories = PgBrandMemoryRepository(session)
        self._personas = PgBrandPersonaRepository(session)
        self._never_say = PgNeverSayRepository(session)
        self._kits = PgBrandKitRepository(session)

    async def get_for_org(
        self, org_id: uuid.UUID, *, profile_id: uuid.UUID | None = None
    ) -> BrandNewsPolicy:
        cfg = load_news_policy_config()
        profile = None
        if profile_id:
            profile = await self._profiles.get(org_id, profile_id)
        if profile is None:
            profile = await self._profiles.get_default(org_id)

        memory = None
        if profile:
            memory = await self._memories.get_active(org_id, profile.id)

        kit = await self._kits.get_by_org_id(org_id)
        never = await self._never_say.get(org_id, profile.id) if profile else None

        dna = (memory.brand_dna_json if memory else None) or {}
        writing = (memory.writing_dna_json if memory else None) or {}
        topics = _labels(dna.get("topics"))
        if not topics:
            topics = _labels((dna.get("detected") or {}).get("topics"))
        industries = _labels(dna.get("industries"))
        # Seed / projection often stores topic labels under industries + visual notes
        if kit and isinstance(kit.tone_json, dict):
            if kit.tone_json.get("industry"):
                industries.append(str(kit.tone_json["industry"]))
        audience = str(
            dna.get("audience")
            or writing.get("reading_level")
            or (kit.tone_json or {}).get("audience")
            or ""
        ).strip()

        expansions = cfg.get("industry_expansions") or {}
        expanded: list[str] = []
        for ind in industries:
            key = ind.lower().replace(" ", "_").replace("-", "_")
            expanded.extend(list(expansions.get(key) or expansions.get(ind.lower()) or []))
            # fuzzy key match
            for ek, terms in expansions.items():
                if ek in key or key in ek:
                    expanded.extend(list(terms or []))

        persona_skills: list[str] = []
        if profile:
            for p in await self._personas.list_for_profile(org_id, profile.id):
                meta = p.metadata_json or {}
                persona_skills.extend(_labels(meta.get("skills")))
                if meta.get("headline"):
                    topics.append(str(meta["headline"]).split("|")[0].strip())

        weight_up = _uniq(
            topics
            + industries
            + expanded
            + persona_skills
            + [
                "Cyber Essentials",
                "DSPT",
                "Microsoft 365",
                "email security",
                "phishing",
                "regulated businesses",
            ]
        )
        weight_down = _uniq(
            list(cfg.get("baseline_exclude") or [])
            + list((never.never_use if never else []) or [])
            + list((never.discouraged if never else []) or [])
            + ["Hybrd", "consumer gadgets", "gaming"]
        )

        baseline = list(cfg.get("baseline_in_scope") or [])
        in_scope = _uniq(baseline + weight_up + expanded, limit=80)
        exclude = _uniq(weight_down, limit=40)

        max_terms = int(cfg.get("max_query_terms") or 8)
        # Prefer concrete searchable phrases for connectors
        query_seeds = _uniq(
            [
                "cybersecurity",
                "managed IT",
                "DSPT",
                "Cyber Essentials",
                "Microsoft 365",
                "phishing",
                "ransomware",
                "data breach",
                "care providers",
                "GDPR",
            ]
            + [t for t in weight_up if len(t) <= 40][:12],
            limit=max_terms,
        )
        primary = build_search_query(query_seeds, max_terms=max_terms)
        alt = [
            build_search_query(
                _uniq(["DSPT", "CQC", "Cyber Essentials", "NHS", "care home cybersecurity"], limit=6),
                max_terms=6,
            ),
            build_search_query(
                _uniq(["phishing", "BEC", "email security", "DMARC", "Microsoft 365"], limit=6),
                max_terms=6,
            ),
        ]

        goal = str(cfg.get("default_strategic_goal") or "").strip()
        if kit and (kit.description or kit.services_line):
            goal = (kit.description or kit.services_line or goal).strip()
        if dna.get("mission"):
            goal = str(dna["mission"]).strip()

        source = "brand_memory" if memory else ("brand_kit" if kit else "defaults")
        return BrandNewsPolicy(
            organization_id=org_id,
            brand_profile_id=profile.id if profile else None,
            topics=_uniq(topics + industries, limit=24),
            industries=_uniq(industries, limit=12),
            audience=audience,
            strategic_goal=goal,
            in_scope_terms=in_scope,
            exclude_terms=exclude,
            primary_query=primary,
            alternate_queries=alt,
            weight_up=weight_up[:30],
            weight_down=weight_down[:20],
            source=source,
        )

    def relevance_profile_markdown(
        self, policy: BrandNewsPolicy, *, brand_name: str = "Brand"
    ) -> str:
        """Full client-profile sections used by RelevanceScorer + generators."""
        up = "\n".join(f"- {t}" for t in policy.weight_up[:25]) or "- (configure Brand Memory topics)"
        down = "\n".join(f"- {t}" for t in policy.weight_down[:20]) or "- celebrity / off-topic consumer news"
        industries = ", ".join(policy.industries) or "managed IT, cybersecurity"
        topics = ", ".join(policy.topics[:16]) or industries
        name = brand_name or "Brand"
        return f"""# Client Profile — Relevance Screening Reference

## 1. The business
{name} — brand-profile driven. Industries: {industries}.
Strategic goal: {policy.strategic_goal or 'Trusted authority in your market.'}

## 2. Target audience
{policy.audience or 'Business owners and operators in the brand industries above.'}
Out of scope: consumer gadget hype, pure developer tooling with no business risk angle, celebrity tech.

## 3. Technical and regulatory scope
Prefer stories about: {topics}.
Credible frameworks/stack derived from Brand Memory (compliance, cloud, security, IT operations).

## 4. Credentials and differentiators
Use Brand Memory credentials and differentiators. Prefer lived experience over slogans.

## 5. Positioning
- Match Brand Memory tone / voice
- Plain English for the stated audience
- Practical examples over fear-mongering

## 6. Relevance test
1. Does this affect the brand's audience and industries?
2. Can {name} credibly comment from Brand Memory scope?
3. Is there a practical lesson or action (not just vendor marketing)?
4. Prefer the brand's geography / regulatory framing when available.

## 7. Weight up / Weight down or exclude
**Weight up**
{up}

**Weight down or exclude**
{down}

## 8. Voice and LinkedIn rules
Follow Brand Memory writing DNA and Never-Say policy. Avoid absolute security guarantees.
CTA style from Brand Memory (conversation / book a call / checker when applicable).
"""

    async def project_relevance_profile(
        self, org_id: uuid.UUID, *, profile_id: uuid.UUID | None = None
    ) -> BrandNewsPolicy:
        """Write brand-derived relevance profile onto Brand Kit.client_profile_md."""
        policy = await self.get_for_org(org_id, profile_id=profile_id)
        kit = await self._kits.get_by_org_id(org_id)
        if not kit:
            logger.warning("No Brand Kit for org %s — skip relevance profile project", org_id)
            return policy
        brand_name = kit.name or "Brand"
        md = self.relevance_profile_markdown(policy, brand_name=brand_name)
        extra = dict(kit.extra_settings or {})
        extra["brand_news_policy"] = {
            "primary_query": policy.primary_query,
            "topics": policy.topics,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "source": policy.source,
        }
        await self._kits.update(
            kit.id,
            {
                "client_profile_md": md,
                "extra_settings": extra,
                "description": policy.strategic_goal[:500] if policy.strategic_goal else kit.description,
            },
        )
        return policy

    async def sync_news_sources(
        self, org_id: uuid.UUID, *, profile_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """Apply brand search queries to connector sources that accept query overrides."""
        policy = await self.project_relevance_profile(org_id, profile_id=profile_id)
        cfg = load_news_policy_config()
        allowed = {str(x).lower() for x in (cfg.get("query_connector_types") or [])}

        result = await self._session.execute(
            select(NewsSource).where(NewsSource.organization_id == org_id)
        )
        sources = list(result.scalars().all())
        updated = 0
        skipped = 0
        details: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()

        for src in sources:
            conf = dict(src.config_json or {})
            connector = (src.connector_type or "").lower()
            accepts = (
                connector in allowed
                or "query" in conf
                or bool(conf.get("brand_query"))
            )
            if not accepts:
                skipped += 1
                continue
            # Prefer brand primary query; keep RSS feeds untouched
            conf["query"] = policy.primary_query
            conf["brand_query"] = True
            conf["brand_queries"] = [policy.primary_query, *policy.alternate_queries]
            conf["brand_topics"] = policy.topics
            conf["brand_synced_at"] = now
            # NewsData categories hint for technology/science when empty
            if connector in {"news_api", "newsdata"} and not conf.get("categories"):
                conf["categories"] = ["technology", "science"]
            src.config_json = conf
            updated += 1
            details.append(
                {
                    "source_id": str(src.id),
                    "name": src.name,
                    "connector_type": src.connector_type,
                    "query": policy.primary_query,
                }
            )

        await self._session.flush()
        logger.info(
            "Brand news policy synced: org=%s updated=%s skipped=%s query=%s",
            org_id,
            updated,
            skipped,
            policy.primary_query[:120],
        )
        return {
            "policy": policy.to_dict(),
            "sources_updated": updated,
            "sources_skipped": skipped,
            "sources": details,
        }
