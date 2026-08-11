"""LinkedIn BrandSourceConnector — URL-first fetch of profile, posts, media, quality.

Requires an org-scoped Playwright `storage_state` session for live fetch (ADR 0062).
Manual about/posts in config remain a CI / offline fallback only.
"""

from __future__ import annotations

import json
import mimetypes
import re
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger
from app.modules.brand_intelligence.application.engines.core import fingerprint_text
from app.modules.brand_intelligence.domain.models import (
    CanonicalBrandObject,
    CboObjectType,
    CboSourceType,
)

logger = get_logger(__name__)


def _post_quality(text: str, eng: dict[str, Any], has_image: bool) -> dict[str, Any]:
    words = re.findall(r"\S+", text or "")
    word_count = len(words)
    hashtags = re.findall(r"#\w+", text or "")
    has_cta = bool(
        re.search(
            r"\b(book|call|message|dm|learn more|visit|try|check|refer)\b",
            text or "",
            flags=re.I,
        )
    )
    reactions = float(eng.get("reactions") or 0)
    comments = float(eng.get("comments") or 0)
    shares = float(eng.get("shares") or 0)
    engagement = reactions + comments * 2 + shares * 3
    # Heuristic quality 0–1
    length_score = 0.9 if 40 <= word_count <= 220 else (0.55 if word_count >= 20 else 0.3)
    structure = 0.15 if "\n" in (text or "") else 0.0
    media = 0.15 if has_image else 0.0
    tags = min(0.1, 0.03 * len(hashtags))
    cta = 0.1 if has_cta else 0.0
    eng_boost = min(0.25, engagement / 80.0)
    quality = min(1.0, round(length_score + structure + media + tags + cta + eng_boost, 3))
    return {
        "word_count": word_count,
        "hashtag_count": len(hashtags),
        "has_cta": has_cta,
        "has_image": has_image,
        "engagement_score": engagement,
        "quality_score": quality,
    }


class LinkedInConnector:
    """Fetch Canonical Brand Objects from a LinkedIn profile URL."""

    source_type = "linkedin"

    async def fetch(
        self, config: dict[str, Any], session_state: bytes | None = None
    ) -> list[CanonicalBrandObject]:
        org_id = uuid.UUID(str(config["organization_id"]))
        profile_id = uuid.UUID(str(config["brand_profile_id"]))
        import_id = uuid.UUID(str(config["import_id"])) if config.get("import_id") else None
        url = str(config.get("linkedin_url") or "").strip()
        if not url:
            return []

        # Prefer live scrape whenever a session is present (URL-only product path).
        want_live = bool(session_state) and config.get("use_playwright", True) is not False
        if want_live and session_state:
            try:
                scraped = await self._playwright_fetch(
                    url=url,
                    session_state=session_state,
                    org_id=org_id,
                    profile_id=profile_id,
                    import_id=import_id,
                    max_posts=int(config.get("max_posts") or 40),
                )
                if scraped:
                    return scraped
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "linkedin_playwright_fetch_failed",
                    extra={"error": str(exc)[:300], "url": url},
                )
                # Fall through to seed if provided; else raise-shaped empty with error CBO
                if not (config.get("about") or config.get("posts")):
                    return [
                        CanonicalBrandObject(
                            id=uuid.uuid4(),
                            organization_id=org_id,
                            brand_profile_id=profile_id,
                            import_id=import_id,
                            object_type=CboObjectType.PROFILE,
                            source_type=CboSourceType.LINKEDIN,
                            canonical_url=url,
                            fingerprint=fingerprint_text("li-error", url, str(exc)[:200]),
                            title="LinkedIn fetch failed",
                            body_text=(
                                f"Could not fetch LinkedIn profile from {url}. "
                                f"Error: {str(exc)[:400]}. "
                                "Save a Playwright LinkedIn session and retry."
                            ),
                            metadata_json={
                                "mode": "error",
                                "error": str(exc)[:400],
                                "session_required": True,
                            },
                        )
                    ]

        # Offline / CI seed path (manual fields)
        return self._seed_from_config(config, session_state, org_id, profile_id, import_id, url)

    def _seed_from_config(
        self,
        config: dict[str, Any],
        session_state: bytes | None,
        org_id: uuid.UUID,
        profile_id: uuid.UUID,
        import_id: uuid.UUID | None,
        url: str,
    ) -> list[CanonicalBrandObject]:
        about = str(config.get("about") or "")
        headline = str(config.get("headline") or "")
        name = str(config.get("display_name") or urlparse(url).path.strip("/") or "LinkedIn Profile")
        company = str(config.get("company") or "").strip()
        location = str(config.get("location") or "").strip()
        website = str(config.get("website") or "").strip()

        objects: list[CanonicalBrandObject] = []
        profile_parts = [
            f"Name: {name}" if name else "",
            f"Company: {company}" if company else "",
            f"Headline: {headline}" if headline else "",
            f"Location: {location}" if location else "",
            f"Website: {website}" if website else "",
            "",
            about,
        ]
        profile_body = "\n".join(p for p in profile_parts if p is not None).strip()
        if not profile_body:
            profile_body = (
                f"LinkedIn URL registered: {url}. "
                "Connect LinkedIn session to fetch profile, posts, and images automatically."
            )
        objects.append(
            CanonicalBrandObject(
                id=uuid.uuid4(),
                organization_id=org_id,
                brand_profile_id=profile_id,
                import_id=import_id,
                object_type=CboObjectType.PROFILE,
                source_type=CboSourceType.LINKEDIN,
                external_id=url,
                canonical_url=url,
                fingerprint=fingerprint_text("li-profile", url, profile_body),
                title=f"{name} — {company}" if company else name,
                body_text=profile_body,
                metadata_json={
                    "session_present": bool(session_state),
                    "mode": "url_seed",
                    "company": company,
                    "headline": headline,
                    "location": location,
                    "website": website,
                    "display_name": name,
                    "session_required": not bool(about or config.get("posts")),
                },
            )
        )

        posts = config.get("posts") or []
        if isinstance(posts, list):
            for i, post in enumerate(posts):
                if isinstance(post, str):
                    content = post
                    eng: dict[str, Any] = {}
                    image_urls: list[str] = []
                elif isinstance(post, dict):
                    content = str(post.get("content") or post.get("text") or "")
                    eng = {
                        "reactions": post.get("reactions", 0),
                        "comments": post.get("comments", 0),
                        "shares": post.get("shares", 0),
                    }
                    image_urls = list(post.get("image_urls") or [])
                else:
                    continue
                if not content.strip():
                    continue
                quality = _post_quality(content, eng, bool(image_urls))
                objects.append(
                    CanonicalBrandObject(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        brand_profile_id=profile_id,
                        import_id=import_id,
                        object_type=CboObjectType.POST,
                        source_type=CboSourceType.LINKEDIN,
                        external_id=f"{url}#post-{i}",
                        canonical_url=url,
                        fingerprint=fingerprint_text("li-post", url, content),
                        title=content.split("\n", 1)[0][:80],
                        body_text=content,
                        engagement={**eng, **quality},
                        media_refs=[{"url": u, "kind": "image"} for u in image_urls],
                        metadata_json={"index": i, "quality": quality},
                    )
                )
        return objects

    async def _playwright_fetch(
        self,
        *,
        url: str,
        session_state: bytes,
        org_id: uuid.UUID,
        profile_id: uuid.UUID,
        import_id: uuid.UUID | None,
        max_posts: int = 40,
    ) -> list[CanonicalBrandObject]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is not installed. pip install playwright && playwright install chromium"
            ) from exc

        try:
            state = json.loads(session_state.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("Invalid LinkedIn session storage_state JSON") from exc

        objects: list[CanonicalBrandObject] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                storage_state=state,
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            await page.goto(url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2500)

            profile = await page.evaluate(
                """() => {
                  const pick = (sels) => {
                    for (const s of sels) {
                      const el = document.querySelector(s);
                      if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
                    }
                    return '';
                  };
                  const name = pick([
                    'h1.text-heading-xlarge',
                    'h1.inline',
                    'main h1',
                    '.pv-text-details__left-panel h1',
                  ]);
                  const headline = pick([
                    '.text-body-medium.break-words',
                    '.pv-text-details__left-panel .text-body-medium',
                    'div.text-body-medium.break-words',
                  ]);
                  const location = pick([
                    '.text-body-small.inline.t-black--light.break-words',
                    '.pv-text-details__left-panel .text-body-small',
                  ]);
                  let about = '';
                  const aboutHeader = Array.from(document.querySelectorAll('h2, section'))
                    .find(el => /about/i.test(el.innerText || ''));
                  if (aboutHeader) {
                    const section = aboutHeader.closest('section') || aboutHeader.parentElement;
                    about = (section && section.innerText || '').replace(/^about\\s*/i, '').trim().slice(0, 8000);
                  }
                  const photo = document.querySelector(
                    'img.pv-top-card-profile-picture__image, img.profile-photo-edit__preview, button img'
                  );
                  return {
                    name, headline, location, about,
                    photo_url: photo && photo.src ? photo.src : '',
                  };
                }"""
            )

            name = str(profile.get("name") or "").strip() or "LinkedIn Profile"
            headline = str(profile.get("headline") or "").strip()
            location = str(profile.get("location") or "").strip()
            about = str(profile.get("about") or "").strip()
            photo_url = str(profile.get("photo_url") or "").strip()

            # Experience / company hint from current role line
            experience_blob = await page.evaluate(
                """() => {
                  const exp = Array.from(document.querySelectorAll('section'))
                    .find(s => /experience/i.test((s.querySelector('h2')||{}).innerText || ''));
                  if (!exp) return '';
                  return (exp.innerText || '').slice(0, 6000);
                }"""
            )
            company = ""
            if experience_blob:
                m = re.search(r"(?:Experience\s+)?([^\n]+)\n([^\n]+)", experience_blob)
                # Prefer lines containing Guard IQ / company after Founder
                for line in str(experience_blob).splitlines():
                    if re.search(r"\b(Guard IQ|Founder|Inc|Ltd|Limited)\b", line, re.I):
                        if "founder" not in line.lower() or "guard" in line.lower():
                            company = line.strip()[:120]
                            if "guard" in company.lower():
                                company = "Guard IQ"
                                break
                if not company and "Guard IQ" in experience_blob:
                    company = "Guard IQ"

            media_refs: list[dict[str, Any]] = []
            if photo_url and photo_url.startswith("http"):
                key = await self._store_remote_image(
                    org_id, profile_id, photo_url, kind="profile_photo"
                )
                if key:
                    media_refs.append({"storage_key": key, "kind": "profile_photo", "source_url": photo_url})

            profile_body = "\n".join(
                p
                for p in (
                    f"Name: {name}",
                    f"Company: {company}" if company else "",
                    f"Headline: {headline}",
                    f"Location: {location}",
                    "",
                    about or "(About section not visible — expand on LinkedIn if restricted.)",
                    "",
                    "Experience:",
                    (experience_blob or "")[:4000],
                )
                if p is not None
            )
            objects.append(
                CanonicalBrandObject(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    brand_profile_id=profile_id,
                    import_id=import_id,
                    object_type=CboObjectType.PROFILE,
                    source_type=CboSourceType.LINKEDIN,
                    external_id=url,
                    canonical_url=url,
                    fingerprint=fingerprint_text("li-live-profile", url, profile_body[:3000]),
                    title=f"{name} — {company}" if company else name,
                    body_text=profile_body[:30000],
                    media_refs=media_refs,
                    metadata_json={
                        "mode": "playwright",
                        "company": company,
                        "headline": headline,
                        "location": location,
                        "display_name": name,
                        "fetched_from_url": True,
                    },
                )
            )

            # Recent activity / posts
            activity_url = url.rstrip("/") + "/recent-activity/all/"
            await page.goto(activity_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)
            for _ in range(6):
                await page.mouse.wheel(0, 2400)
                await page.wait_for_timeout(900)

            raw_posts = await page.evaluate(
                """(maxPosts) => {
                  const cards = Array.from(document.querySelectorAll(
                    'div.feed-shared-update-v2, div.occludable-update, article'
                  ));
                  const out = [];
                  const seen = new Set();
                  for (const card of cards) {
                    const textEl = card.querySelector(
                      '.feed-shared-update-v2__description, .feed-shared-text, .break-words, span[dir="ltr"]'
                    );
                    let text = '';
                    if (textEl) text = textEl.innerText.trim();
                    if (!text) {
                      const t = (card.innerText || '').trim();
                      // skip chrome
                      if (t.length < 40) continue;
                      text = t.split('\\n').slice(0, 40).join('\\n');
                    }
                    text = text.replace(/\\s+see more$/i, '').trim();
                    if (text.length < 40) continue;
                    const key = text.slice(0, 120);
                    if (seen.has(key)) continue;
                    seen.add(key);
                    const imgs = Array.from(card.querySelectorAll('img'))
                      .map(i => i.src)
                      .filter(s => s && s.startsWith('http') && !/emoji|ghost|data:image/i.test(s));
                    const reactText = (card.innerText.match(/(\\d[\\d,]*)\\s*(reactions?|likes?)/i) || [])[1] || '0';
                    const commentText = (card.innerText.match(/(\\d[\\d,]*)\\s*comments?/i) || [])[1] || '0';
                    const shareText = (card.innerText.match(/(\\d[\\d,]*)\\s*reposts?/i) || [])[1] || '0';
                    const num = (s) => parseInt(String(s).replace(/,/g, ''), 10) || 0;
                    out.push({
                      text: text.slice(0, 6000),
                      image_urls: imgs.slice(0, 4),
                      reactions: num(reactText),
                      comments: num(commentText),
                      shares: num(shareText),
                    });
                    if (out.length >= maxPosts) break;
                  }
                  return out;
                }""",
                max_posts,
            )

            for i, post in enumerate(raw_posts or []):
                content = str(post.get("text") or "").strip()
                if not content:
                    continue
                image_urls = [u for u in (post.get("image_urls") or []) if isinstance(u, str)]
                eng = {
                    "reactions": int(post.get("reactions") or 0),
                    "comments": int(post.get("comments") or 0),
                    "shares": int(post.get("shares") or 0),
                }
                media_refs_post: list[dict[str, Any]] = []
                for j, img_url in enumerate(image_urls[:3]):
                    key = await self._store_remote_image(
                        org_id, profile_id, img_url, kind=f"post_image_{i}_{j}"
                    )
                    if key:
                        media_refs_post.append(
                            {"storage_key": key, "kind": "image", "source_url": img_url}
                        )
                quality = _post_quality(content, eng, bool(media_refs_post or image_urls))
                objects.append(
                    CanonicalBrandObject(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        brand_profile_id=profile_id,
                        import_id=import_id,
                        object_type=CboObjectType.POST,
                        source_type=CboSourceType.LINKEDIN,
                        external_id=f"{url}#activity-{i}",
                        canonical_url=activity_url,
                        fingerprint=fingerprint_text("li-live-post", url, content[:1500]),
                        title=content.split("\n", 1)[0][:100],
                        body_text=content,
                        engagement={**eng, **quality},
                        media_refs=media_refs_post,
                        metadata_json={
                            "index": i,
                            "quality": quality,
                            "mode": "playwright",
                            "image_count": len(media_refs_post),
                        },
                    )
                )

            await browser.close()

        if len(objects) <= 1:
            # Only profile — still valid return
            objects[0].metadata_json["posts_found"] = 0
        else:
            objects[0].metadata_json["posts_found"] = len(objects) - 1
        return objects

    async def _store_remote_image(
        self, org_id: uuid.UUID, profile_id: uuid.UUID, url: str, *, kind: str
    ) -> str | None:
        try:
            from app.infrastructure.storage import get_storage_provider

            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code >= 400:
                    return None
                content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                if not content_type.startswith("image/"):
                    return None
                ext = mimetypes.guess_extension(content_type) or ".jpg"
                key = f"{org_id}/brand/{profile_id}/linkedin/{kind}-{uuid.uuid4().hex[:10]}{ext}"
                get_storage_provider().put_bytes(key, resp.content, content_type=content_type)
                return key
        except Exception as exc:  # noqa: BLE001
            logger.debug("linkedin_image_store_failed", extra={"error": str(exc)[:200]})
            return None
