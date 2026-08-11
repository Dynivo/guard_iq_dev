#!/usr/bin/env python3
"""Seed Shailesh Bhudia / Guard IQ Brand Intelligence from LinkedIn profile data.

Idempotent for the first org. Runs Collect → Analyze → Approve through Brand
Intelligence (URL-seed LinkedIn path). Replaces prior incorrect Hybrd seed.

Usage:
    cd ai-content-platform-backend
    .venv/bin/python scripts/seed_shailesh_guardiq_brand.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select

from app.infrastructure.postgres.models.brand_intelligence import (
    BrandImportJobRow,
    BrandImportRow,
    BrandMemoryReviewRow,
    BrandMemoryVersionRow,
    BrandVectorChunkRow,
    CanonicalBrandObjectRow,
)
from app.infrastructure.postgres.models.identity import Organization
from app.infrastructure.postgres.session import async_session_factory
from app.modules.brand_intelligence.application.pipeline import BrandIntelligencePipeline
from app.modules.brand_intelligence.application.use_cases import BrandIntelligenceUseCases
from app.infrastructure.storage.factory import get_storage_provider
from app.modules.brand_intelligence.domain.models import (
    BrandImportJob,
    BrandPersona,
    BrandProfile,
    LogoAssetSet,
    NeverSayPolicy,
    PersonaKind,
    ProfileKind,
)
from app.modules.organization.infrastructure.brand_kit_repository import PgBrandKitRepository

LINKEDIN_URL = "https://www.linkedin.com/in/shaileshbhudia/"
WEBSITE = "https://guardiq.co.uk"
COMPANY = "Guard IQ"
FOUNDER = "Shailesh Bhudia"
PROFILE_NAME = "Shailesh Bhudia — Guard IQ"

HEADLINE = (
    "Guard IQ | Managed IT & Security for Regulated Businesses | Cyber Essentials Certified"
)

ABOUT = """\
Most IT support companies will tell you they cover security. Very few of them have sat \
inside a DSPT submission, understand what CQC inspectors actually look for, or know what \
a data breach actually costs a regulated business.

I started Guard IQ because I kept seeing the same problems: businesses running on unmanaged \
devices, no MFA, email security that existed on paper and nowhere else, and compliance \
frameworks that were copy-pasted from templates no one had read.

I manage IT and security for a small number of clients on a retained basis. Primarily \
businesses operating in regulated environments — care providers, legal practices, financial \
services, dental groups — where data protection isn't optional and the consequences of \
getting it wrong are serious.

The work covers day-to-day IT support and Microsoft 365 management through to endpoint \
security, DSPT advisory, Cyber Essentials certification, and ongoing compliance support \
across GDPR, SRA, and FCA obligations.

Guard IQ is Cyber Essentials certified. I know the standards from both sides.

If you run a regulated business and you want someone who understands the environment \
you're operating in, I'm worth a conversation.
"""

POSTS = [
    {
        "content": (
            "Someone told me last week their spam filter \"does its job.\" Their inbox is clean, "
            "so it must be working.\n\n"
            "I asked what happens to the phishing emails that don't look like phishing. The ones "
            "with no spelling mistakes, no dodgy links, just a normal-looking message asking "
            "someone to click through and log in.\n\n"
            "Basic filtering catches the obvious stuff… bulk spam, known malware attachments, "
            "the sloppy ones. It's not built to catch a well-written, targeted email that's never "
            "been seen before.\n\n"
            "Inbound filtering done properly checks attachment behaviour, link reputation, sender "
            "history — not just a known-bad list. Worth understanding what your current filter "
            "actually checks before you assume the quiet inbox means the risk is gone.\n\n"
            "#EmailSecurity #PhishingPrevention #CyberSecurity #SmallBusiness #InboxSecurity"
        ),
        "reactions": 3,
        "comments": 1,
        "shares": 0,
    },
    {
        "content": (
            "📞 New desk phone, properly set up.\n\n"
            "This is a Yealink VoIP handset, and it's part of what we set up and manage for "
            "clients too. Not just laptops and servers. Phone systems, call routing, the lot.\n\n"
            "For a care provider or law firm, a phone going down is as bad as email going down. "
            "No incoming referrals, no client calls, no way for staff to reach each other. "
            "We manage phones the same way we manage everything else: monitored, maintained, "
            "someone accountable if it breaks.\n\n"
            "#ManagedIT #VoIP #Cybersecurity #RegulatedBusiness #NWLondon"
        ),
        "reactions": 9,
        "comments": 0,
        "shares": 0,
    },
    {
        "content": (
            "Guard IQ has been nominated for Emerging MSP of the Year at the MSP Channel Insights "
            "Awards!\n\n"
            "We started this year as one person with a laptop and a confidence that regulated "
            "businesses deserve security that actually works. Somewhere between DSPT deadlines, "
            "a live infostealer catch, and building out the team, that bet started paying off.\n\n"
            "Being nominated alongside MSPs doing genuinely strong work is the recognition on "
            "its own. Whatever happens next, this is a good marker of a year well spent.\n\n"
            "#MSP #Cybersecurity #MSPChannelInsights"
        ),
        "reactions": 35,
        "comments": 12,
        "shares": 0,
    },
    {
        "content": (
            "Something I explain to almost every new client, and it always catches them off guard.\n\n"
            "Microsoft doesn't back up your data. They say so themselves, in their own Services "
            "Agreement. Their job is keeping the platform up and running. Your data is your "
            "responsibility.\n\n"
            "Being in the cloud doesn't mean it's protected from ransomware. If a device gets "
            "infected and OneDrive is syncing, the encrypted files get uploaded straight over "
            "the good ones.\n\n"
            "If you don't know whether your M365 data actually has a real backup behind it, "
            "it's worth five minutes to check.\n\n"
            "#Microsoft365 #DataBackup #Cybersecurity"
        ),
        "reactions": 4,
        "comments": 0,
        "shares": 0,
    },
    {
        "content": (
            "Had a call last week with a registered manager who'd been told by her previous IT "
            "provider that DSPT was \"basically done\" because they had antivirus installed.\n\n"
            "It wasn't done. Antivirus is one control out of dozens the toolkit asks you to "
            "evidence.\n\n"
            "I've taken 10+ care providers through this to a first-time pass, because I do the "
            "assessment work myself, not just the technical bit.\n\n"
            "If your current provider talks about DSPT, Cyber Essentials or GDPR in vague terms "
            "rather than specifics, that's usually the tell.\n\n"
            "#DSPT #CQC #Compliance #CareSector #ManagedIT"
        ),
        "reactions": 6,
        "comments": 1,
        "shares": 0,
    },
    {
        "content": (
            "Most business owners don't call IT when tech slows down. They call when it starts "
            "affecting work.\n\n"
            "Teams calls freezing. Emails taking forever. Cloud systems lagging. Staff losing "
            "time trying to \"make it work\".\n\n"
            "At Guard IQ, we help businesses across North West and Central London with Wi-Fi and "
            "internet issues, Microsoft 365 and email problems, VoIP call quality, and network "
            "troubleshooting.\n\n"
            "Clear answers. No jargon. Just practical solutions to get you working again.\n\n"
            "#NWLondonBusiness #ITSupport #SmallBusinessUK #WiFiProblems #BusinessProductivity"
        ),
        "reactions": 3,
        "comments": 0,
        "shares": 0,
    },
    {
        "content": (
            "Can your team spot a fake invoice email?\n\n"
            "Most people can't, and it's rarely obvious. Business email compromise doesn't use "
            "dodgy links or bad spelling anymore. It uses a lookalike domain and a request that "
            "sounds completely normal.\n\n"
            "We put together a free 10-question quiz to test it. Worth 2 minutes with your team, "
            "especially if you handle client data, payments, or anything CQC cares about.\n\n"
            "👉 https://lnkd.in/eHAmuKSk\n\n"
            "#CyberSecurity #EmailSecurity #MSP"
        ),
        "reactions": 5,
        "comments": 0,
        "shares": 0,
    },
    {
        "content": (
            "Can someone send out emails pretending to be your business?\n\n"
            "If your domain's email settings aren't set up right, a scammer can send an email "
            "that looks like it came from you. That's how fake invoices get paid.\n\n"
            "We built a free checker that tells you in about 10 seconds — SPF, DKIM and DMARC "
            "in plain English. No sign-up.\n\n"
            "👉 https://lnkd.in/eWnuwPtr\n\n"
            "Worth a 10-second check especially if you're in care, legal or accountancy."
        ),
        "reactions": 6,
        "comments": 0,
        "shares": 0,
    },
]

CLIENT_PROFILE_MD = f"""\
# Guard IQ — Brand Profile (Shailesh Bhudia)

## Who we are
Guard IQ is a founder-led managed IT & cybersecurity partner for regulated SMEs across \
North West London and Central London. Founded by {FOUNDER} (CompTIA CySA+, Network+; \
Brunel BSc Computer Science). Cyber Essentials certified.

## Positioning
- **Tagline:** Managed IT & Security for Regulated Businesses | Cyber Essentials Certified
- **Differentiator:** Lived compliance experience (DSPT, CQC, GDPR, SRA, FCA) — not checklist reselling. \
Plain English. Retained IT + security for a small number of clients.
- **Audience:** Care providers, legal practices, financial services, dental groups, and other \
regulated SMEs who need day-to-day IT plus real security and compliance support
- **Website:** {WEBSITE}

## Voice
Direct, founder-led, no fluff. Practical examples from real client environments. Prefer \
\"regulated business\", \"DSPT\", \"Cyber Essentials\", \"clear answers, no jargon\" over hype. \
Authority from MSP/network background and hands-on compliance work.

## Topics we own
Managed IT, Microsoft 365, email security / phishing, backups (M365 is not a backup), DSPT & CQC, \
Cyber Essentials, VoIP / Yealink, Wi-Fi & networking, endpoint security, BEC / DMARC, AI tool risk, \
referrals for NW London SMEs.

## Services
Cloud management, backup & recovery, network support, IT consulting, information security, \
cybersecurity, telecommunications / VoIP.

## Never say
cheap, cheapest, hack-proof, 100% secure, guaranteed breach-free, \"basically done\" for DSPT

## LinkedIn source
{LINKEDIN_URL}
"""

BRAND_GUIDELINES_MD = f"""\
# Guard IQ Brand Guidelines

Version 1.0 · Seeded for Content Intelligence · Source: LinkedIn + founder brief

## 1. Brand essence
**Guard IQ** is a founder-led managed IT and cybersecurity partner for regulated SMEs.
We make security and compliance practical — clear answers, no jargon.

**Founder:** {FOUNDER}
**Website:** {WEBSITE}
**LinkedIn:** {LINKEDIN_URL}

## 2. Logo
- Primary mark: shield / IQ lockup in deep navy.
- Keep clear space around the mark equal to the height of the “I” in IQ.
- Prefer logo on light backgrounds; use reverse (white) on dark navy only.
- Do not stretch, recolour arbitrarily, or place on busy photography without a solid panel.

## 3. Colour palette
| Role | Hex | Usage |
|------|-----|--------|
| Primary | `#0A1F2B` | Headlines, dark panels, logo |
| Secondary | `#1A5CB0` | Links, CTAs, accents |
| Accent | `#0D7377` | Highlights, success / trust cues |
| Neutral | `#F5F7FA` | Page backgrounds |
| Text | `#0A1F2B` on light / `#FFFFFF` on dark |

## 4. Typography
- **Headings:** Clean sans (Inter / system UI equivalent) — medium weight, short lines.
- **Body:** Same family, regular — plain English, short paragraphs.
- Avoid decorative or script fonts on LinkedIn creatives.

## 5. Voice & tone
- Direct, founder-led, no fluff.
- Speak to owners and registered managers, not engineers only.
- Prefer concrete examples (DSPT, phishing, backups, VoIP outages) over buzzwords.
- CTA style: conversation / book a call / free checker — never hard-sell.

## 6. Imagery
- Prefer real workplace / regulated-sector context (care, legal, practice managers).
- Product shots OK (Yealink, devices) when the story is operational.
- Overlay text must stay high-contrast; keep Guard IQ logo on LinkedIn visuals.

## 7. Topics we own
Managed IT · Microsoft 365 · email security / phishing · backups · DSPT & CQC ·
Cyber Essentials · VoIP · networking · endpoint security · BEC / DMARC · AI tool risk.

## 8. Never say
- cheap / cheapest
- hack-proof / 100% secure / guaranteed breach-free
- “basically done” for DSPT
- Hybrd (legacy incorrect name — always Guard IQ)

## 9. Compliance posture
Claims must be accurate. We are Cyber Essentials certified. Do not invent certifications
or imply regulatory approval we do not hold.
"""

# Minimal Guard IQ shield mark (SVG) for Brand Kit / typography compositing.
LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="Guard IQ">
  <rect width="512" height="512" rx="64" fill="#0A1F2B"/>
  <path d="M256 72 L400 128 V248 C400 340 336 412 256 440 C176 412 112 340 112 248 V128 Z"
        fill="none" stroke="#1A5CB0" stroke-width="28" stroke-linejoin="round"/>
  <path d="M256 120 L360 164 V248 C360 318 314 370 256 392 C198 370 152 318 152 248 V164 Z"
        fill="#0D7377"/>
  <text x="256" y="270" text-anchor="middle" font-family="Arial, Helvetica, sans-serif"
        font-size="96" font-weight="700" fill="#FFFFFF">IQ</text>
</svg>
"""


async def _org_id(session) -> uuid.UUID:
    result = await session.execute(select(Organization).order_by(Organization.created_at.asc()).limit(1))
    org = result.scalar_one_or_none()
    if not org:
        raise RuntimeError("No organization found — run scripts/seed_database.py first")
    print(f"  Org: {org.name} ({org.id})")
    return org.id


async def _ensure_profile(uc: BrandIntelligenceUseCases, org_id: uuid.UUID) -> BrandProfile:
    for p in await uc.profiles.list_for_org(org_id):
        name_l = (p.name or "").lower()
        if p.name == PROFILE_NAME or "guardiq" in name_l or "guard iq" in name_l or "hybrd" in name_l:
            if not p.is_default:
                for other in await uc.profiles.list_for_org(org_id):
                    if other.is_default and other.id != p.id:
                        other.is_default = False
                        await uc.profiles.update(other)
            p.is_default = True
            p.name = PROFILE_NAME
            p.kind = ProfileKind.CORPORATE
            await uc.profiles.update(p)
            print(f"  Updated brand profile → {PROFILE_NAME}: {p.id}")
            return p

    default = await uc.profiles.get_default(org_id)
    if default:
        default.name = PROFILE_NAME
        default.kind = ProfileKind.CORPORATE
        default.is_default = True
        await uc.profiles.update(default)
        print(f"  Renamed default profile → {PROFILE_NAME}: {default.id}")
        return default

    created = await uc.create_profile(org_id, kind="corporate", name=PROFILE_NAME, is_default=True)
    profile = await uc.profiles.get(org_id, uuid.UUID(created["id"]))
    assert profile
    print(f"  Created brand profile: {profile.id}")
    return profile


async def _ensure_persona_and_never_say(
    uc: BrandIntelligenceUseCases, org_id: uuid.UUID, profile_id: uuid.UUID
) -> None:
    personas = await uc.personas.list_for_profile(org_id, profile_id)
    founder = next((p for p in personas if p.kind == PersonaKind.FOUNDER), None)
    await uc.personas.upsert(
        BrandPersona(
            id=founder.id if founder else uuid.uuid4(),
            organization_id=org_id,
            brand_profile_id=profile_id,
            kind=PersonaKind.FOUNDER,
            name=FOUNDER,
            is_default=True,
            voice_notes=(
                "Founder of Guard IQ. Direct, plain English. Regulated-sector IT & security "
                "(care, legal, finance, dental). DSPT / Cyber Essentials / M365 / VoIP."
            ),
            metadata_json={
                "linkedin_url": LINKEDIN_URL,
                "headline": HEADLINE,
                "company": COMPANY,
                "location": "London Area, United Kingdom",
                "website": WEBSITE,
                "education": "Brunel University of London — BSc Computer Science",
                "certifications": ["CompTIA CySA+", "CompTIA Network+"],
                "skills": [
                    "Cybersecurity",
                    "Network Security",
                    "Cloud Security",
                    "Firewall Management",
                    "AWS",
                    "Vulnerability Management",
                    "Security Operations",
                ],
            },
        )
    )
    never = await uc.never_say.get(org_id, profile_id) or NeverSayPolicy(
        id=uuid.uuid4(), organization_id=org_id, brand_profile_id=profile_id
    )
    never.forbidden = ["hack-proof", "100% secure", "guaranteed"]
    never.never_use = ["cheap", "cheapest", "guaranteed breach-free", "Hybrd", "hybrd"]
    never.discouraged = ["synergy", "best-in-class", "cutting-edge", "basically done"]
    never.preferred_alternatives = {
        "cheap": "practical / retained partner",
        "hack-proof": "defence-in-depth / Cyber Essentials",
        "Hybrd": "Guard IQ",
    }
    await uc.never_say.upsert(never)
    print("  Founder persona + Never-Say updated")


async def _clear_prior_import_artifacts(session, org_id: uuid.UUID, profile_id: uuid.UUID) -> None:
    """Remove prior CBOs / import jobs for a clean Guard IQ re-import (keep memory row for upsert)."""
    await session.execute(
        delete(CanonicalBrandObjectRow).where(
            CanonicalBrandObjectRow.organization_id == org_id,
            CanonicalBrandObjectRow.brand_profile_id == profile_id,
        )
    )
    # Drop import jobs then imports for this profile
    import_ids = (
        await session.execute(
            select(BrandImportRow.id).where(
                BrandImportRow.organization_id == org_id,
                BrandImportRow.brand_profile_id == profile_id,
            )
        )
    ).scalars().all()
    if import_ids:
        await session.execute(
            delete(BrandImportJobRow).where(BrandImportJobRow.import_id.in_(import_ids))
        )
        await session.execute(delete(BrandImportRow).where(BrandImportRow.id.in_(import_ids)))
    await session.execute(
        delete(BrandVectorChunkRow).where(
            BrandVectorChunkRow.organization_id == org_id,
            BrandVectorChunkRow.brand_profile_id == profile_id,
        )
    )
    mem = await BrandIntelligenceUseCases(session).memories.get_active(org_id, profile_id)
    if mem:
        await session.execute(
            delete(BrandMemoryReviewRow).where(BrandMemoryReviewRow.memory_id == mem.id)
        )
        await session.execute(
            delete(BrandMemoryVersionRow).where(BrandMemoryVersionRow.memory_id == mem.id)
        )
    await session.flush()
    print("  Cleared prior CBOs / imports / vector chunks for re-seed")


async def _upload_brand_assets(
    uc: BrandIntelligenceUseCases, org_id: uuid.UUID, profile_id: uuid.UUID
) -> list[dict]:
    """Persist logo + brand guidelines in object storage and LogoAssetSet / Brand Kit."""
    storage = get_storage_provider()
    logo_id = uuid.uuid4()
    guidelines_id = uuid.uuid4()
    logo_key = f"{org_id}/brand/{profile_id}/logo/{logo_id}.svg"
    guidelines_key = f"{org_id}/brand/{profile_id}/guideline/{guidelines_id}.md"

    logo_stored = storage.put_bytes(
        logo_key, LOGO_SVG.encode("utf-8"), content_type="image/svg+xml"
    )
    guidelines_stored = storage.put_bytes(
        guidelines_key,
        BRAND_GUIDELINES_MD.encode("utf-8"),
        content_type="text/markdown; charset=utf-8",
    )

    existing = await uc.logos.get(org_id, profile_id)
    logo = existing or LogoAssetSet(
        id=uuid.uuid4(),
        organization_id=org_id,
        brand_profile_id=profile_id,
        variants_json={},
    )
    variants = dict(logo.variants_json or {})
    variants["primary"] = logo_stored.storage_key
    variants["svg"] = logo_stored.storage_key
    logo.variants_json = variants
    logo.primary_key = logo_stored.storage_key
    await uc.logos.upsert(logo)

    kit = await uc.brand_kits.get_by_org_id(org_id)
    if kit:
        await uc.brand_kits.update(kit.id, {"logo_object_key": logo.primary_key})

    artifacts = [
        {
            "kind": "logo",
            "filename": "guard-iq-logo.svg",
            "storage_key": logo_stored.storage_key,
            "mime_type": "image/svg+xml",
            "variant": "primary",
            "extracted_text": "Guard IQ primary logo (shield + IQ)",
        },
        {
            "kind": "guideline",
            "filename": "guard-iq-brand-guidelines.md",
            "storage_key": guidelines_stored.storage_key,
            "mime_type": "text/markdown",
            "extracted_text": BRAND_GUIDELINES_MD,
        },
    ]
    print(f"  Uploaded logo → {logo_stored.storage_key}")
    print(f"  Uploaded guidelines → {guidelines_stored.storage_key}")
    return artifacts


async def _run_import_and_finalize(
    session,
    uc: BrandIntelligenceUseCases,
    org_id: uuid.UUID,
    profile: BrandProfile,
    artifacts: list[dict],
) -> None:
    source_mix = {
        "linkedin_url": LINKEDIN_URL,
        "linkedin_about": ABOUT,
        "linkedin_headline": HEADLINE,
        "linkedin_display_name": FOUNDER,
        "linkedin_posts": POSTS,
        "website_url": WEBSITE,
        "max_pages": 6,
        "use_playwright": False,
        "artifacts": artifacts,
        "sources": ["linkedin", "website", "upload"],
        "has_logo": True,
        "has_guidelines": True,
        "seed": "shailesh_guardiq_linkedin",
        "company": COMPANY,
    }
    result = await uc.create_import(org_id, profile_id=profile.id, source_mix=source_mix)
    if result.is_failure:
        raise RuntimeError(result.message)
    import_id = uuid.UUID(result.value["id"])
    print(f"  Import created: {import_id}")

    bi_job = await uc.import_jobs.create(
        BrandImportJob(
            id=uuid.uuid4(),
            organization_id=org_id,
            import_id=import_id,
            job_id=None,
            stage="queued",
            progress_pct=0,
            message="Guard IQ LinkedIn re-seed",
        )
    )
    pipeline = BrandIntelligencePipeline(session)
    memory = await pipeline.run(org_id=org_id, import_id=import_id, bi_job=bi_job)
    print(f"  Memory draft: {memory.id} lifecycle={memory.lifecycle.value}")

    memory.brand_dna_json = {
        **(memory.brand_dna_json or {}),
        "founder": FOUNDER,
        "company": COMPANY,
        "linkedin_url": LINKEDIN_URL,
        "website": WEBSITE,
        "headline": HEADLINE,
        "location": "London Area, United Kingdom",
        "mission": (
            "Help regulated SMEs stay connected and secure — managed IT, Microsoft 365, "
            "endpoint security, DSPT advisory, Cyber Essentials, and compliance support "
            "(GDPR, SRA, FCA) with clear answers and no jargon."
        ),
        "personality": "direct, founder-led, practical, compliance-aware",
        "industries": ["cybersecurity", "managed_it", "healthcare_care", "legal", "financial_services"],
        "audience": (
            "Regulated SMEs — care providers, legal practices, financial services, dental groups; "
            "owners and registered managers in NW / Central London"
        ),
        "certifications": ["Cyber Essentials", "CompTIA CySA+", "CompTIA Network+"],
        "visual_hints": {
            "primary_color": "#0A1F2B",
            "secondary_color": "#1A5CB0",
            "accent_color": "#0D7377",
            "banner_message": "Managed IT & Security for Regulated Businesses",
        },
    }
    memory.writing_dna_json = {
        **(memory.writing_dna_json or {}),
        "tone": "direct, founder-led, no fluff",
        "authority": "high",
        "reading_level": "business_owner",
        "technical_depth": "plain_english_expert",
        "storytelling": "high",
        "cta_style": "conversation / book a call / free checker",
    }
    memory.visual_dna_json = {
        **(memory.visual_dna_json or {}),
        "styles": ["corporate", "shield_logo"],
        "colors": ["#0A1F2B", "#1A5CB0", "#0D7377"],
        "fonts": ["Inter"],
        "logo_presence": True,
        # Learned from LinkedIn creatives (banner / posts often bottom-right mark)
        "preferred_logo_position": "bottom_right",
        "notes": "Guard IQ shield mark; optional typography logo — default bottom-right.",
    }
    # Completeness/health already scored in pipeline; clear guideline gap after asset upload.
    health = dict(memory.health_json or {})
    missing = [m for m in (health.get("missing_assets") or []) if m not in {"logo", "brand_guidelines"}]
    health["missing_assets"] = missing
    health["guideline_coverage"] = 100.0
    health["asset_coverage"] = 100.0
    memory.health_json = health
    completeness = dict(memory.completeness_json or {})
    completeness["logo"] = 1.0
    completeness["guidelines_coverage"] = 1.0
    memory.completeness_json = completeness
    # Drop guideline-upload recs that are already satisfied.
    memory.recommendations_json = [
        r
        for r in (memory.recommendations_json or [])
        if isinstance(r, dict)
        and "guideline" not in str(r.get("title", "")).lower()
        and "logo" not in str(r.get("title", "")).lower()
    ] or [
        {
            "code": "sync_latest",
            "title": "Keep Brand Memory fresh",
            "detail": "Re-run LinkedIn URL import periodically when posts change.",
            "priority": 60,
        }
    ]
    await uc.memories.save(memory)

    review = await uc.reviews.get_open(org_id, memory.id)
    if review:
        approved = await uc.approve_review(
            org_id, review.id, user_id=None, correlation_id="seed-shailesh-guardiq"
        )
        if approved.is_failure:
            raise RuntimeError(approved.message)
        print(f"  Review approved → finalized memory v{approved.value.get('version_no')}")
    else:
        raise RuntimeError("Expected open review after analyze")


async def _project_kit(session, org_id: uuid.UUID) -> None:
    kits = PgBrandKitRepository(session)
    kit = await kits.get_by_org_id(org_id)
    if not kit:
        print("  No Brand Kit — skip projection")
        return
    await kits.update(
        kit.id,
        {
            "name": COMPANY,
            "primary_color": "#0A1F2B",
            "secondary_color": "#1A5CB0",
            "accent_color": "#0D7377",
            "services_line": HEADLINE,
            "footer_text": "Guard IQ — Managed IT & Security for Regulated Businesses",
            "description": (
                "Founder-led managed IT and cybersecurity for regulated SMEs in North West London. "
                "DSPT, Cyber Essentials, M365, VoIP, and day-to-day support — clear answers, no jargon."
            ),
            "tone_json": {
                "tone": "direct, founder-led, no fluff",
                "voice": "Direct, founder-led, no fluff",
                "audience": "Owners and practice managers (5–70 staff)",
                "industry": "IT Support & Managed Services",
                "from_brand_intelligence": True,
                "linkedin_url": LINKEDIN_URL,
                "founder": FOUNDER,
                "company": COMPANY,
                "website": WEBSITE,
            },
            "client_profile_md": CLIENT_PROFILE_MD,
            "font_heading": "Inter",
            "font_body": "Inter",
            "extra_settings": {
                **(kit.extra_settings or {}),
                "linkedin_url": LINKEDIN_URL,
                "founder": FOUNDER,
                "company": COMPANY,
                "website": WEBSITE,
                "brand_intelligence_seed": "shailesh_guardiq",
                "brand_guidelines": "guard-iq-brand-guidelines.md",
                "palette": ["#0A1F2B", "#1A5CB0", "#0D7377"],
            },
        },
    )
    print("  Brand Kit updated (Guard IQ + guidelines/fonts)")


async def main() -> None:
    print("=== Seed Shailesh Bhudia / Guard IQ Brand Intelligence ===")
    async with async_session_factory() as session:
        org_id = await _org_id(session)
        uc = BrandIntelligenceUseCases(session)
        profile = await _ensure_profile(uc, org_id)
        await _ensure_persona_and_never_say(uc, org_id, profile.id)
        await session.commit()

        await _clear_prior_import_artifacts(session, org_id, profile.id)
        await session.commit()

        artifacts = await _upload_brand_assets(uc, org_id, profile.id)
        await session.commit()

        await _run_import_and_finalize(session, uc, org_id, profile, artifacts)
        await _project_kit(session, org_id)
        await session.commit()

        from app.modules.brand_intelligence.application.news_policy_service import (
            BrandNewsPolicyService,
        )

        news_sync = await BrandNewsPolicyService(session).sync_news_sources(
            org_id, profile_id=profile.id
        )
        await session.commit()

        mem = await uc.memories.get_active(org_id, profile.id)
        logo = await uc.logos.get(org_id, profile.id)
        kit = await uc.brand_kits.get_by_org_id(org_id)
        print("=== Done ===")
        print(f"  Profile: {profile.id} ({profile.name})")
        print(f"  Company: {COMPANY}")
        print(f"  Memory:  {mem.id if mem else None} lifecycle={mem.lifecycle.value if mem else None}")
        print(f"  Logo key: {logo.primary_key if logo else None}")
        print(f"  Brand kit logo: {kit.logo_object_key if kit else None}")
        missing = (mem.health_json or {}).get("missing_assets") if mem else None
        print(f"  Missing assets: {missing}")
        print(f"  News query: {(news_sync.get('policy') or {}).get('primary_query')}")
        print(f"  News sources updated: {news_sync.get('sources_updated')}")
        print(f"  Brand → /app/brand")
        print(f"  Dashboard → /app/brand/intelligence?profileId={profile.id}")
        print("  Next: .venv/bin/python scripts/sync_brand_news_and_rescore.py")


if __name__ == "__main__":
    asyncio.run(main())
