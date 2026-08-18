#!/usr/bin/env python3
"""Seed the database with the default organization, admin user, brand kit,
starter news sources, default provider configs, and client profile.

Idempotent — skips rows that already exist (keyed on email / slug / name).
Run after `alembic upgrade head`.

Usage:
    python scripts/seed_database.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security.password import hash_password
from app.infrastructure.postgres.session import async_session_factory
from app.infrastructure.postgres.models.identity import Membership, Organization, User
from app.infrastructure.postgres.models.branding import BrandKit
from app.infrastructure.postgres.models.ai_ops import ProviderConfig
from app.infrastructure.postgres.models.intelligence import Claim
from app.infrastructure.postgres.models.brand_intelligence import BrandProfileRow, BrandPersonaRow, NeverSayPolicyRow
from app.modules.brand_intelligence.domain.models import ProfileKind, PersonaKind


ORG_NAME = "Guard IQ"
ORG_SLUG = "guardiq"
ADMIN_EMAIL = "admin@guardiq.com"
ADMIN_DISPLAY_NAME = "Admin"
# Legacy seed email rejected by EmailStr (.local is reserved) — migrate on re-seed.
_LEGACY_ADMIN_EMAIL = "admin@guardiq.local"


def _admin_password() -> str:
    password = get_settings().SEED_ADMIN_PASSWORD.strip()
    if len(password) < 12:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD must be set to a unique value of at least "
            "12 characters before creating or migrating the admin account"
        )
    return password


async def _ensure_org(session: AsyncSession) -> uuid.UUID:
    result = await session.execute(select(Organization).where(Organization.slug == ORG_SLUG))
    org = result.scalar_one_or_none()
    if org:
        print(f"  Organization '{ORG_NAME}' already exists: {org.id}")
        return org.id

    org_id = uuid.uuid4()
    session.add(Organization(id=org_id, name=ORG_NAME, slug=ORG_SLUG))
    await session.flush()
    print(f"  Created organization '{ORG_NAME}': {org_id}")
    return org_id


async def _ensure_admin(session: AsyncSession, org_id: uuid.UUID) -> uuid.UUID:
    result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
    user = result.scalar_one_or_none()
    if user:
        print(f"  Admin user already exists: {user.id}")
        return user.id

    legacy = await session.execute(select(User).where(User.email == _LEGACY_ADMIN_EMAIL))
    legacy_user = legacy.scalar_one_or_none()
    if legacy_user:
        legacy_user.email = ADMIN_EMAIL
        legacy_user.password_hash = hash_password(_admin_password())
        await session.flush()
        print(f"  Migrated admin email {_LEGACY_ADMIN_EMAIL} -> {ADMIN_EMAIL}: {legacy_user.id}")
        return legacy_user.id

    user_id = uuid.uuid4()
    session.add(
        User(
            id=user_id,
            organization_id=org_id,
            email=ADMIN_EMAIL,
            display_name=ADMIN_DISPLAY_NAME,
            password_hash=hash_password(_admin_password()),
        )
    )
    await session.flush()
    print(f"  Created admin user: {user_id}")

    session.add(
        Membership(
            user_id=user_id,
            organization_id=org_id,
            role="owner",
        )
    )
    await session.flush()
    print("  Created owner membership")
    return user_id


# Brand-kit settings that only ever lived in the DB, so a reset silently
# reverted them and made working features look broken. Most important is
# default_image_count=2: at 1 the second ("white card") infographic variant
# is never generated at all.
DEFAULT_BRAND_EXTRA_SETTINGS: dict = {
    "default_image_count": 2,
    "auto_generate_image_with_draft": True,
    "publishing_window": "fortnight",
    "publishing_targets": {
        "educational": 6,
        "success_story": 3,
        "personal_achievement": 1,
    },
}


async def _ensure_brand_kit(session: AsyncSession, org_id: uuid.UUID) -> None:
    from pathlib import Path

    profile_path = Path(__file__).resolve().parents[1] / "configs" / "brand" / "client-profile.md"
    profile_md = profile_path.read_text(encoding="utf-8") if profile_path.exists() else None

    result = await session.execute(
        select(BrandKit).where(BrandKit.organization_id == org_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        changed = []
        if profile_md and not (existing.client_profile_md or "").strip():
            existing.client_profile_md = profile_md
            changed.append("client_profile_md")
        merged = {**DEFAULT_BRAND_EXTRA_SETTINGS, **(existing.extra_settings or {})}
        if merged != (existing.extra_settings or {}):
            existing.extra_settings = merged
            changed.append("extra_settings")
        if changed:
            await session.flush()
            print(f"  Backfilled brand kit: {', '.join(changed)}")
        else:
            print("  Brand kit already exists")
        return

    session.add(
        BrandKit(
            extra_settings=dict(DEFAULT_BRAND_EXTRA_SETTINGS),
            organization_id=org_id,
            name="Guard IQ",
            primary_color="#0A1F2B",
            secondary_color="#1A5CB0",
            accent_color="#0D7377",
            font_heading="Inter",
            font_body="Inter",
            tone_json={
                "voice": "direct, founder-led, no fluff",
                "style": "practical and educational",
                "positioning": "security-led IT for regulated businesses",
                "avoid": ["clickbait", "jargon", "fear-mongering"],
            },
            footer_text="Guard IQ — Managed IT & Security for Regulated Businesses",
            services_line="IT Support | Cybersecurity | Compliance",
            client_profile_path="configs/brand/client-profile.md",
            client_profile_md=profile_md,
            description=(
                "Founder-led managed IT and cybersecurity for regulated SMEs in "
                "North West and Central London."
            ),
        )
    )
    await session.flush()
    print("  Created brand kit")


async def _ensure_news_sources(session: AsyncSession, org_id: uuid.UUID) -> None:
    from app.modules.news.application.source_seed import ensure_catalog_sources

    counts = await ensure_catalog_sources(session, org_id)
    print(
        f"  Enterprise news catalog: created={counts['created']} "
        f"updated={counts['updated']}"
    )


async def _ensure_provider_configs(session: AsyncSession, org_id: uuid.UUID) -> None:
    configs = [
        {"capability": "relevance", "provider": "gemini", "model": "gemini-flash-latest", "priority": 0},
        {"capability": "planning", "provider": "gemini", "model": "gemini-flash-latest", "priority": 0},
        {"capability": "copywriting", "provider": "gemini", "model": "gemini-flash-latest", "priority": 0},
        {"capability": "carousel_copy", "provider": "gemini", "model": "gemini-flash-latest", "priority": 0},
        {"capability": "image_prompt", "provider": "gemini", "model": "gemini-flash-latest", "priority": 0},
        {"capability": "preference_summary", "provider": "gemini", "model": "gemini-flash-latest", "priority": 0},
    ]
    for cfg in configs:
        result = await session.execute(
            select(ProviderConfig).where(
                ProviderConfig.organization_id == org_id,
                ProviderConfig.capability == cfg["capability"],
            )
        )
        if result.scalar_one_or_none():
            print(f"  Provider config '{cfg['capability']}' already exists")
            continue

        session.add(ProviderConfig(organization_id=org_id, **cfg))
        await session.flush()
        print(f"  Created provider config: {cfg['capability']} -> {cfg['provider']}/{cfg['model']}")


async def _ensure_seed_claims(session: AsyncSession, org_id: uuid.UUID) -> None:
    claims = [
        {
            "text": "Infostealer malware contained in 8 minutes",
            "provenance": "Client operational data — founder's own monitoring logs",
            "source_type": "operational",
            "confidence": 1.0,
        },
        {
            "text": "Cyber Essentials certification achieved within one week",
            "provenance": "Recurring client engagements — multiple documented instances",
            "source_type": "operational",
            "confidence": 1.0,
        },
    ]
    for claim_data in claims:
        result = await session.execute(
            select(Claim).where(
                Claim.organization_id == org_id,
                Claim.text == claim_data["text"],
            )
        )
        if result.scalar_one_or_none():
            print(f"  Claim already exists: {claim_data['text'][:50]}...")
            continue

        session.add(Claim(organization_id=org_id, **claim_data))
        await session.flush()
        print(f"  Created claim: {claim_data['text'][:50]}...")


async def _ensure_default_brand_profile(session: AsyncSession, org_id: uuid.UUID) -> None:
    result = await session.execute(
        select(BrandProfileRow).where(
            BrandProfileRow.organization_id == org_id,
            BrandProfileRow.is_default.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile:
        print(f"  Default brand profile already exists: {profile.id}")
        return
    profile_id = uuid.uuid4()
    session.add(
        BrandProfileRow(
            id=profile_id,
            organization_id=org_id,
            kind=ProfileKind.CORPORATE.value,
            name="Corporate",
            is_default=True,
        )
    )
    await session.flush()
    session.add(
        BrandPersonaRow(
            id=uuid.uuid4(),
            organization_id=org_id,
            brand_profile_id=profile_id,
            kind=PersonaKind.CEO.value,
            name="CEO",
            is_default=True,
        )
    )
    session.add(
        NeverSayPolicyRow(
            id=uuid.uuid4(),
            organization_id=org_id,
            brand_profile_id=profile_id,
        )
    )
    await session.flush()
    print(f"  Created default Corporate brand profile: {profile_id}")


async def seed() -> None:
    print("=== Seeding database ===")
    async with async_session_factory() as session:
        org_id = await _ensure_org(session)
        await _ensure_admin(session, org_id)
        await _ensure_brand_kit(session, org_id)
        await _ensure_news_sources(session, org_id)
        await _ensure_provider_configs(session, org_id)
        await _ensure_seed_claims(session, org_id)
        await _ensure_default_brand_profile(session, org_id)
        await session.commit()
    # Complete the one-time Guard IQ projection (founder persona, approved
    # brand memory, supplied logo and guidelines). The helper skips safely
    # once the projection marker is present, so the main seed stays idempotent.
    from scripts.seed_shailesh_guardiq_brand import seed_guard_iq_brand

    await seed_guard_iq_brand()
    print("=== Seed complete ===")


if __name__ == "__main__":
    asyncio.run(seed())
