"""Publishing Plan — brand weekly/fortnight mix, quota gaps, regenerate."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.constants import ArticleStatus, DraftStatus
from app.core.logging import get_logger
from app.infrastructure.postgres.models.branding import BrandKit
from app.infrastructure.postgres.models.carousel import MediaAsset
from app.infrastructure.postgres.models.capture import CaptureSession
from app.infrastructure.postgres.models.content import Draft
from app.infrastructure.postgres.models.intelligence import RelevanceScore
from app.infrastructure.postgres.models.news import Article
from app.modules.content.application.use_cases import GenerateDraftUseCase
from app.modules.image.application.gallery_assets import select_gallery_media

logger = get_logger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[4] / "configs" / "content" / "publishing_plan.yaml"

MIX_KEYS = ("educational", "success_story", "personal_achievement")
WINDOW_MODES = ("weekly", "fortnight")
_WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri")


class CaptureGeneratePort(Protocol):
    async def execute(self, org_id: uuid.UUID, session_id: uuid.UUID) -> dict: ...


@dataclass(frozen=True, slots=True)
class PublishingPlanTargets:
    educational: int = 6
    success_story: int = 3
    personal_achievement: int = 1

    @property
    def total(self) -> int:
        return self.educational + self.success_story + self.personal_achievement

    def as_dict(self) -> dict[str, int]:
        return {
            "educational": self.educational,
            "success_story": self.success_story,
            "personal_achievement": self.personal_achievement,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class PublishingPlanConfig:
    default_window: str
    windows: dict[str, PublishingPlanTargets]
    targets: PublishingPlanTargets
    counting_statuses: tuple[str, ...]
    educational_article_statuses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedOrgPlan:
    mode: str
    targets: PublishingPlanTargets


def _targets_from_mapping(raw: dict[str, Any] | None, *, defaults: PublishingPlanTargets) -> PublishingPlanTargets:
    t = raw or {}
    return PublishingPlanTargets(
        educational=max(0, min(10, int(t.get("educational", defaults.educational)))),
        success_story=max(0, min(10, int(t.get("success_story", defaults.success_story)))),
        personal_achievement=max(
            0, min(5, int(t.get("personal_achievement", defaults.personal_achievement)))
        ),
    )


@lru_cache(maxsize=1)
def load_publishing_plan_config() -> PublishingPlanConfig:
    raw: dict[str, Any] = {}
    if _CONFIG_PATH.is_file():
        raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}

    legacy = PublishingPlanTargets(
        educational=int((raw.get("targets") or {}).get("educational", 6)),
        success_story=int((raw.get("targets") or {}).get("success_story", 3)),
        personal_achievement=int((raw.get("targets") or {}).get("personal_achievement", 1)),
    )
    win_raw = raw.get("windows") or {}
    weekly_defaults = PublishingPlanTargets(educational=3, success_story=1, personal_achievement=1)
    fortnight_defaults = legacy
    windows = {
        "weekly": _targets_from_mapping(
            (win_raw.get("weekly") or {}).get("targets"), defaults=weekly_defaults
        ),
        "fortnight": _targets_from_mapping(
            (win_raw.get("fortnight") or {}).get("targets"), defaults=fortnight_defaults
        ),
    }
    default_window = str(raw.get("default_window") or "fortnight").strip().lower()
    if default_window not in WINDOW_MODES:
        default_window = "fortnight"

    statuses = tuple(
        str(s)
        for s in (
            raw.get("counting_statuses")
            or [
                DraftStatus.PENDING_REVIEW,
                DraftStatus.APPROVED,
                "scheduled",
                DraftStatus.PUBLISHED,
                DraftStatus.IN_REVIEW,
            ]
        )
    )
    article_statuses = tuple(
        str(s)
        for s in (
            raw.get("educational_article_statuses")
            or [ArticleStatus.RELEVANT, ArticleStatus.SCORED]
        )
    )
    return PublishingPlanConfig(
        default_window=default_window,
        windows=windows,
        targets=windows["fortnight"],
        counting_statuses=statuses,
        educational_article_statuses=article_statuses,
    )


def monday_of_week(d: date) -> date:
    """Return Monday of the ISO calendar week containing ``d``."""
    return d - timedelta(days=d.weekday())


def weekly_window(today: date | None = None) -> tuple[date, date]:
    """This calendar week Mon–Fri."""
    today = today or date.today()
    start = monday_of_week(today)
    end = start + timedelta(days=4)
    return start, end


def fortnight_window(today: date | None = None) -> tuple[date, date]:
    """Current + next calendar week, Mon–Fri.

    Returns (Monday of this week, Friday of next week).
    """
    today = today or date.today()
    start = monday_of_week(today)
    end = start + timedelta(days=11)  # Friday of next week
    return start, end


def plan_window(mode: str, today: date | None = None) -> tuple[date, date]:
    if str(mode).strip().lower() == "weekly":
        return weekly_window(today)
    return fortnight_window(today)


def workdays_in_window(start: date, end: date) -> list[date]:
    """Mon–Fri dates inclusive within [start, end]."""
    days: list[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


# Backward-compatible aliases
workdays_in_fortnight = workdays_in_window


def days_left_in_window(today: date | None = None, *, end: date | None = None) -> int:
    today = today or date.today()
    if end is None:
        _, end = fortnight_window(today)
    remaining = 0
    cur = today
    while cur <= end:
        if cur.weekday() < 5:
            remaining += 1
        cur += timedelta(days=1)
    return remaining


days_left_in_fortnight = days_left_in_window


def empty_counts() -> dict[str, int]:
    return {k: 0 for k in MIX_KEYS}


def compute_gaps(targets: dict[str, int], counts: dict[str, int]) -> dict[str, int]:
    return {
        k: max(0, int(targets.get(k, 0)) - int(counts.get(k, 0)))
        for k in MIX_KEYS
    }


PLAN_ORIGIN = "content_intelligence_plan"


def is_plan_origin(meta: dict[str, Any] | None) -> bool:
    """True only for AI Content Intelligence plan posts (not manual News drafts)."""
    if not isinstance(meta, dict):
        return False
    if meta.get("plan_origin") is True:
        return True
    return str(meta.get("origin") or "") == PLAN_ORIGIN


def normalize_mix_type(content_type: str | None) -> str | None:
    """Map draft content_type onto a mix bucket, or None if out of mix."""
    if not content_type:
        return None
    ct = content_type.strip().lower()
    if ct in MIX_KEYS:
        return ct
    if ct in {
        "thought_leadership",
        "industry_news",
        "best_practices",
        "checklist",
        "security_alert",
        "compliance_update",
        "regulatory_update",
        "threat_alert",
        "faq",
        "weekly_roundup",
        "single_post",
        "carousel",
    }:
        return "educational"
    if ct in {"case_study", "customer_story"}:
        return "success_story"
    return None


def _window_bounds_utc(start: date, end: date) -> tuple[datetime, datetime]:
    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, 23, 59, 59, 999999, tzinfo=timezone.utc)
    return start_dt, end_dt


def resolve_targets_for_mode(
    config: PublishingPlanConfig,
    mode: str,
    brand_targets: dict[str, Any] | None = None,
) -> PublishingPlanTargets:
    m = mode if mode in WINDOW_MODES else config.default_window
    base = config.windows.get(m) or config.targets
    if brand_targets and isinstance(brand_targets, dict):
        return _targets_from_mapping(brand_targets, defaults=base)
    return base


class PublishingPlanService:
    """DB-backed mix status, educational fill, and full plan regenerate."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        config: PublishingPlanConfig | None = None,
        generate_uc: GenerateDraftUseCase | None = None,
        capture_generate: CaptureGeneratePort | None = None,
    ) -> None:
        self._session = session
        self._config = config or load_publishing_plan_config()
        self._generate_uc = generate_uc
        self._capture_generate = capture_generate

    async def resolve_org_plan(
        self,
        org_id: uuid.UUID,
    ) -> ResolvedOrgPlan:
        kit = (
            await self._session.execute(
                select(BrandKit).where(BrandKit.organization_id == org_id).limit(1)
            )
        ).scalar_one_or_none()
        extra = dict(kit.extra_settings or {}) if kit else {}
        mode = str(extra.get("publishing_window") or self._config.default_window).strip().lower()
        if mode not in WINDOW_MODES:
            mode = self._config.default_window
        brand_targets = extra.get("publishing_targets")
        if not isinstance(brand_targets, dict):
            brand_targets = None
        targets = resolve_targets_for_mode(self._config, mode, brand_targets)
        return ResolvedOrgPlan(mode=mode, targets=targets)

    async def get_plan(
        self,
        org_id: uuid.UUID,
        *,
        today: date | None = None,
    ) -> dict[str, Any]:
        today = today or date.today()
        resolved = await self.resolve_org_plan(org_id)
        start, end = plan_window(resolved.mode, today)
        workdays = workdays_in_window(start, end)
        targets = resolved.targets.as_dict()
        drafts = await self._fetch_window_drafts(org_id, start, end)

        counts = empty_counts()
        by_date: dict[str, list[str]] = {d.isoformat(): [] for d in workdays}
        draft_by_id: dict[str, Draft] = {}
        review_drafts: list[Draft] = []

        # Only AI Content Intelligence plan posts count — not manual News drafts.
        for d in drafts:
            meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
            if not is_plan_origin(meta):
                continue
            draft_by_id[str(d.id)] = d
            bucket = normalize_mix_type(d.content_type)
            if bucket:
                counts[bucket] = counts.get(bucket, 0) + 1
            scheduled = meta.get("scheduled_for")
            is_placeable = d.status in (
                DraftStatus.APPROVED,
                DraftStatus.PUBLISHED,
                "approved",
                "published",
            )
            if is_placeable and isinstance(scheduled, str) and scheduled[:10] in by_date:
                by_date[scheduled[:10]].append(str(d.id))
            if d.status in (
                DraftStatus.PENDING_REVIEW,
                DraftStatus.IN_REVIEW,
                "pending_review",
                "in_review",
            ):
                review_drafts.append(d)

        if len(review_drafts) < 12:
            extra = await self._fetch_recent_review_drafts(
                org_id, exclude={d.id for d in review_drafts}, limit=12 - len(review_drafts)
            )
            for d in extra:
                meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
                if is_plan_origin(meta):
                    review_drafts.append(d)

        review_items = await self._serialize_review_queue(org_id, review_drafts[:12])
        gaps = compute_gaps(targets, counts)
        slots = self._build_slots(workdays, by_date, draft_by_id, gaps)
        total_count = sum(counts.values())
        return {
            "window": {
                "mode": resolved.mode,
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            "target": targets,
            "counts": counts,
            "gaps": gaps,
            "total_count": total_count,
            "days_left": days_left_in_window(today, end=end),
            "workdays": [
                {
                    "date": d.isoformat(),
                    "label": _WEEKDAY_LABELS[d.weekday()],
                    "draft_ids": by_date.get(d.isoformat(), []),
                }
                for d in workdays
            ],
            "slots": slots,
            "review_queue": review_items,
            "needs_capture": {
                k: gaps[k]
                for k in ("success_story", "personal_achievement")
                if gaps.get(k, 0) > 0
            },
        }

    def _build_slots(
        self,
        workdays: list[date],
        by_date: dict[str, list[str]],
        draft_by_id: dict[str, Draft],
        gaps: dict[str, int],
    ) -> list[dict[str, Any]]:
        # Round-robin across mix types so suggestions spread through the window
        # instead of stacking every educational slot before success/personal ones.
        remaining = {key: int(gaps.get(key, 0)) for key in MIX_KEYS}
        needed_queue: list[str] = []
        while any(remaining.values()):
            for key in MIX_KEYS:
                if remaining[key] > 0:
                    needed_queue.append(key)
                    remaining[key] -= 1
        ni = 0
        slots: list[dict[str, Any]] = []
        for d in workdays:
            key = d.isoformat()
            ids = list(by_date.get(key) or [])
            items: list[dict[str, Any]] = []
            for did in ids:
                draft = draft_by_id.get(did)
                items.append(
                    {
                        "draft_id": did,
                        "content_type": draft.content_type if draft else None,
                        "status": draft.status if draft else None,
                        "suggested_date": key,
                    }
                )
            suggested_ct = None
            if not ids and ni < len(needed_queue):
                suggested_ct = needed_queue[ni]
                ni += 1
            slots.append(
                {
                    "date": key,
                    "label": _WEEKDAY_LABELS[d.weekday()],
                    "draft_ids": ids,
                    "items": items,
                    "open": len(ids) == 0,
                    "suggested_content_type": suggested_ct,
                }
            )
        return slots

    async def list_educational_ideas(
        self,
        org_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Top relevant/scored articles not yet used for a draft."""
        articles = await self._candidate_educational_articles(org_id, limit=limit)
        return [
            {
                "id": str(a.id),
                "title": a.title,
                "summary": a.summary,
                "status": a.status,
                "relevance_score": score,
            }
            for a, score in articles
        ]

    async def fill_educational(
        self,
        org_id: uuid.UUID,
        *,
        today: date | None = None,
        max_generate: int | None = None,
        ensure_image: bool = False,
    ) -> dict[str, Any]:
        """Generate educational drafts until the educational gap is filled."""
        plan = await self.get_plan(org_id, today=today)
        gap = int(plan["gaps"].get("educational", 0))
        mode = (plan.get("window") or {}).get("mode") or "fortnight"
        if gap <= 0:
            return {
                "generated": [],
                "skipped_already_drafted": 0,
                "gap_remaining": 0,
                "message": f"Educational quota already filled for this {mode}",
            }

        n = gap if max_generate is None else min(gap, max_generate)
        candidates = await self._candidate_educational_articles(org_id, limit=max(n * 3, n))
        generate = self._generate_uc or GenerateDraftUseCase(self._session)

        generated: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for article, _score in candidates:
            if len(generated) >= n:
                break
            try:
                draft = await generate.execute(
                    org_id=org_id,
                    article_id=article.id,
                    content_type="educational",
                    origin=PLAN_ORIGIN,
                )
                draft_id = draft.get("id")
                image_meta = draft.get("image_generation")
                if ensure_image and draft_id and not image_meta:
                    image_meta = await self._ensure_draft_image(
                        org_id, uuid.UUID(str(draft_id)), reason="plan_regenerate"
                    )
                generated.append(
                    {
                        "draft_id": draft_id,
                        "article_id": str(article.id),
                        "title": article.title,
                        "content_type": "educational",
                        "image_generation": image_meta,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "fill-educational failed article_id=%s err=%s",
                    article.id,
                    exc,
                )
                errors.append({"article_id": str(article.id), "error": str(exc)})

        remaining = max(0, gap - len(generated))
        return {
            "generated": generated,
            "errors": errors,
            "gap_remaining": remaining,
            "requested": n,
            "message": f"Generated {len(generated)} educational draft(s)",
        }

    async def regenerate_plan(
        self,
        org_id: uuid.UUID,
        *,
        today: date | None = None,
        max_generate: int | None = None,
    ) -> dict[str, Any]:
        """Fill mix gaps: educational from news, success/personal from ready Capture."""
        edu = await self.fill_educational(
            org_id,
            today=today,
            max_generate=max_generate,
            ensure_image=True,
        )
        generated = list(edu.get("generated") or [])
        errors = list(edu.get("errors") or [])

        plan_mid = await self.get_plan(org_id, today=today)
        from_capture: list[dict[str, Any]] = []
        capture_budget = max_generate
        if capture_budget is not None:
            capture_budget = max(0, capture_budget - len(generated))

        for content_type in ("success_story", "personal_achievement"):
            gap = int(plan_mid["gaps"].get(content_type, 0))
            if gap <= 0:
                continue
            n = gap if capture_budget is None else min(gap, capture_budget)
            if n <= 0:
                continue
            sessions = await self._ready_capture_sessions(org_id, content_type, limit=n)
            capture_uc = self._capture_generate
            if capture_uc is None:
                from app.modules.capture.application.use_cases import GenerateFromCaptureUseCase

                capture_uc = GenerateFromCaptureUseCase(self._session)

            filled = 0
            for sess in sessions:
                if filled >= n:
                    break
                try:
                    result = await capture_uc.execute(org_id, sess.id)
                    draft_id = result.get("id")
                    photo_count = int(result.get("photo_count") or 0)
                    if draft_id:
                        await self._mark_plan_origin(uuid.UUID(str(draft_id)))
                    image_meta = None
                    if draft_id and photo_count <= 0:
                        image_meta = await self._ensure_draft_image(
                            org_id, uuid.UUID(str(draft_id)), reason="plan_regenerate_capture"
                        )
                    item = {
                        "draft_id": draft_id,
                        "capture_session_id": str(sess.id),
                        "content_type": content_type,
                        "title": sess.title,
                        "image_generation": image_meta,
                        "photo_count": photo_count,
                    }
                    from_capture.append(item)
                    generated.append(item)
                    filled += 1
                    if capture_budget is not None:
                        capture_budget = max(0, capture_budget - 1)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "regenerate capture failed session_id=%s err=%s",
                        sess.id,
                        exc,
                    )
                    errors.append(
                        {
                            "capture_session_id": str(sess.id),
                            "content_type": content_type,
                            "error": str(exc),
                        }
                    )

            plan_mid = await self.get_plan(org_id, today=today)

        seeded = await self.seed_calendar(org_id, today=today)
        plan = await self.get_plan(org_id, today=today)
        gaps = plan.get("gaps") or {}
        needs_capture = {
            k: int(gaps.get(k, 0))
            for k in ("success_story", "personal_achievement")
            if int(gaps.get(k, 0)) > 0
        }
        return {
            "generated": generated,
            "from_capture": from_capture,
            "errors": errors,
            "calendar_seeded": seeded,
            "gaps_remaining": gaps,
            "needs_capture": needs_capture,
            "message": (
                f"Regenerated plan: {len(generated)} LinkedIn-ready post(s) "
                f"({len(from_capture)} from Capture); "
                f"calendar labeled {seeded.get('assigned', 0)} post(s)"
            ),
            "plan": {
                "counts": plan["counts"],
                "gaps": plan["gaps"],
                "total_count": plan["total_count"],
                "target": plan["target"],
                "window": plan["window"],
                "slots": plan["slots"],
                "days_left": plan["days_left"],
                "needs_capture": needs_capture,
                "review_queue": plan["review_queue"],
            },
        }

    async def seed_calendar(
        self,
        org_id: uuid.UUID,
        *,
        today: date | None = None,
        rebalance: bool = False,
    ) -> dict[str, Any]:
        """Assign plan-origin drafts onto workdays; strip manual News drafts from calendar.

        Only Content Intelligence plan posts (AI-selected for the mix) are labeled.
        Manually generated News drafts stay in Drafts but do not appear on the plan calendar.
        """
        today = today or date.today()
        resolved = await self.resolve_org_plan(org_id)
        start, end = plan_window(resolved.mode, today)
        workdays = workdays_in_window(start, end)
        targets = resolved.targets.as_dict()
        if not workdays:
            return {"assigned": 0, "skipped": 0, "cleared_manual": 0, "workdays": 0, "assignments": []}

        # Only approved (or already published) posts are placed on the calendar —
        # pending-review drafts still need a decision in the review queue first.
        placeable_statuses = (
            DraftStatus.APPROVED,
            DraftStatus.PUBLISHED,
            "approved",
            "published",
        )
        rows = (
            await self._session.execute(
                select(Draft)
                .where(
                    Draft.organization_id == org_id,
                    Draft.status.in_(placeable_statuses),
                )
                .order_by(Draft.created_at.desc())
                .limit(300)
            )
        ).scalars().all()

        load: dict[str, int] = {d.isoformat(): 0 for d in workdays}
        to_place: list[Draft] = []
        skipped = 0
        cleared_manual = 0
        placed_by_mix = empty_counts()

        for d in rows:
            meta = dict(d.metadata_json or {}) if isinstance(d.metadata_json, dict) else {}
            scheduled = meta.get("scheduled_for")
            if not is_plan_origin(meta):
                # Remove calendar placement from manual News drafts
                if isinstance(scheduled, str) or meta.get("calendar_seeded"):
                    meta.pop("scheduled_for", None)
                    meta.pop("calendar_label", None)
                    meta.pop("calendar_seeded", None)
                    d.metadata_json = meta
                    flag_modified(d, "metadata_json")
                    cleared_manual += 1
                continue

            if isinstance(scheduled, str) and len(scheduled) >= 10:
                day = scheduled[:10]
                if day in load and not rebalance:
                    load[day] += 1
                    bucket = normalize_mix_type(d.content_type)
                    if bucket:
                        placed_by_mix[bucket] = placed_by_mix.get(bucket, 0) + 1
                    skipped += 1
                    continue
                if rebalance:
                    try:
                        sd = date.fromisoformat(day)
                    except ValueError:
                        sd = None
                    if sd is not None and start <= sd <= end and day in load:
                        load[day] += 1
                        bucket = normalize_mix_type(d.content_type)
                        if bucket:
                            placed_by_mix[bucket] = placed_by_mix.get(bucket, 0) + 1
                        skipped += 1
                        continue
            to_place.append(d)

        mix_rank = {"educational": 0, "success_story": 1, "personal_achievement": 2}

        def _sort_key(draft: Draft) -> tuple[int, str]:
            bucket = normalize_mix_type(draft.content_type) or "zzz"
            return (mix_rank.get(bucket, 9), draft.created_at.isoformat() if draft.created_at else "")

        to_place.sort(key=_sort_key)

        assignments: list[dict[str, Any]] = []
        day_cycle = list(workdays)
        for draft in to_place:
            bucket = normalize_mix_type(draft.content_type) or "educational"
            # Respect mix targets — do not overload calendar beyond brand requirements
            if placed_by_mix.get(bucket, 0) >= int(targets.get(bucket, 0)):
                continue
            day = min(day_cycle, key=lambda d: (load[d.isoformat()], d.toordinal()))
            day_key = day.isoformat()
            meta = dict(draft.metadata_json or {})
            mix = bucket
            meta["scheduled_for"] = day_key
            meta["calendar_label"] = mix
            meta["calendar_seeded"] = True
            meta["plan_origin"] = True
            meta["origin"] = PLAN_ORIGIN
            draft.metadata_json = meta
            flag_modified(draft, "metadata_json")
            load[day_key] += 1
            placed_by_mix[bucket] = placed_by_mix.get(bucket, 0) + 1
            assignments.append(
                {
                    "draft_id": str(draft.id),
                    "date": day_key,
                    "content_type": draft.content_type,
                    "mix_type": mix,
                    "title": (draft.hook or "").strip()[:120] or "Untitled post",
                }
            )

        if assignments or cleared_manual:
            await self._session.flush()
        logger.info(
            "Calendar seeded org_id=%s assigned=%s skipped=%s cleared_manual=%s window=%s→%s",
            org_id,
            len(assignments),
            skipped,
            cleared_manual,
            start,
            end,
        )
        return {
            "assigned": len(assignments),
            "skipped": skipped,
            "cleared_manual": cleared_manual,
            "workdays": len(workdays),
            "window": {"mode": resolved.mode, "start": start.isoformat(), "end": end.isoformat()},
            "load": load,
            "assignments": assignments,
        }

    async def clear_calendar(self, org_id: uuid.UUID) -> dict[str, Any]:
        """Unschedule every plan-origin draft — full reset, drafts themselves are untouched."""
        rows = (
            await self._session.execute(
                select(Draft).where(Draft.organization_id == org_id)
            )
        ).scalars().all()

        cleared = 0
        for d in rows:
            meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
            if not is_plan_origin(meta):
                continue
            if not (meta.get("scheduled_for") or meta.get("calendar_seeded")):
                continue
            meta = dict(meta)
            meta.pop("scheduled_for", None)
            meta.pop("calendar_label", None)
            meta.pop("calendar_seeded", None)
            d.metadata_json = meta
            flag_modified(d, "metadata_json")
            cleared += 1

        if cleared:
            await self._session.flush()
        logger.info("Calendar cleared org_id=%s cleared=%s", org_id, cleared)
        return {"cleared": cleared}

    async def _mark_plan_origin(self, draft_id: uuid.UUID) -> None:
        draft = await self._session.get(Draft, draft_id)
        if draft is None:
            return
        meta = dict(draft.metadata_json or {})
        meta["plan_origin"] = True
        meta["origin"] = PLAN_ORIGIN
        draft.metadata_json = meta
        flag_modified(draft, "metadata_json")
        await self._session.flush()

    async def _ensure_draft_image(
        self,
        org_id: uuid.UUID,
        draft_id: uuid.UUID,
        *,
        reason: str,
    ) -> dict[str, Any] | None:
        try:
            from app.modules.image.application.queue_generation import queue_async_image_generation

            return await queue_async_image_generation(
                self._session,
                org_id=org_id,
                draft_id=draft_id,
                count=1,
                reason=reason,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ensure image failed draft_id=%s err=%s", draft_id, exc)
            return None

    async def _ready_capture_sessions(
        self,
        org_id: uuid.UUID,
        content_type: str,
        *,
        limit: int,
    ) -> list[CaptureSession]:
        if limit <= 0:
            return []
        stmt = (
            select(CaptureSession)
            .where(
                CaptureSession.organization_id == org_id,
                CaptureSession.content_type == content_type,
                CaptureSession.draft_id.is_(None),
                CaptureSession.raw_text.is_not(None),
                CaptureSession.raw_text != "",
                ~CaptureSession.status.in_(("completed", "generating")),
            )
            .order_by(CaptureSession.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def _fetch_recent_review_drafts(
        self,
        org_id: uuid.UUID,
        *,
        exclude: set[uuid.UUID],
        limit: int,
    ) -> list[Draft]:
        if limit <= 0:
            return []
        stmt = (
            select(Draft)
            .where(
                Draft.organization_id == org_id,
                Draft.status.in_(
                    (
                        DraftStatus.PENDING_REVIEW,
                        DraftStatus.IN_REVIEW,
                        "pending_review",
                        "in_review",
                    )
                ),
            )
            .order_by(Draft.created_at.desc())
            .limit(limit + len(exclude))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        out: list[Draft] = []
        for d in rows:
            if d.id in exclude:
                continue
            out.append(d)
            if len(out) >= limit:
                break
        return out

    async def _serialize_review_queue(
        self, org_id: uuid.UUID, drafts: list[Draft]
    ) -> list[dict[str, Any]]:
        """LinkedIn-ready review cards: copy + primary image (if ready)."""
        if not drafts:
            return []
        ids = [d.id for d in drafts]
        media_rows = (
            await self._session.execute(
                select(MediaAsset)
                .where(
                    MediaAsset.organization_id == org_id,
                    MediaAsset.draft_id.in_(ids),
                    MediaAsset.kind.in_(("generated_illustration", "capture_photo")),
                )
                .order_by(MediaAsset.created_at.desc())
            )
        ).scalars().all()
        by_draft: dict[uuid.UUID, list[MediaAsset]] = {}
        for m in media_rows:
            if m.draft_id is None:
                continue
            by_draft.setdefault(m.draft_id, []).append(m)

        items: list[dict[str, Any]] = []
        for d in drafts:
            meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
            ig = meta.get("image_generation") if isinstance(meta.get("image_generation"), dict) else {}
            body = (d.edited_text or d.generated_text or "")[:600]
            medias = by_draft.get(d.id) or []
            capture = [m for m in medias if m.kind == "capture_photo"]
            ai = select_gallery_media([m for m in medias if m.kind == "generated_illustration"])
            primary = (capture + ai)[0] if (capture or ai) else None
            image_url = None
            if primary and primary.object_key:
                image_url = f"/media/objects/{primary.object_key}"
            items.append(
                {
                    "id": str(d.id),
                    "hook": d.hook,
                    "body": body,
                    "cta": d.cta,
                    "hashtags": list(d.hashtags_json or [])[:12],
                    "content_type": d.content_type,
                    "status": d.status,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "image_url": image_url,
                    "image_generating": str(ig.get("status") or "") == "running",
                    "article_id": str(d.article_id) if d.article_id else None,
                }
            )
        return items

    async def _fetch_window_drafts(
        self,
        org_id: uuid.UUID,
        start: date,
        end: date,
    ) -> list[Draft]:
        start_dt, end_dt = _window_bounds_utc(start, end)
        statuses = list(self._config.counting_statuses)
        stmt = (
            select(Draft)
            .where(
                Draft.organization_id == org_id,
                Draft.status.in_(statuses),
            )
            .order_by(Draft.created_at.desc())
            .limit(500)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        out: list[Draft] = []
        seen: set[uuid.UUID] = set()
        for d in rows:
            if d.id in seen:
                continue
            meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
            scheduled = meta.get("scheduled_for")
            created_in = bool(d.created_at and start_dt <= d.created_at <= end_dt)
            scheduled_in = False
            if isinstance(scheduled, str):
                try:
                    sd = date.fromisoformat(scheduled[:10])
                    scheduled_in = start <= sd <= end
                except ValueError:
                    scheduled_in = False
            if created_in or scheduled_in:
                seen.add(d.id)
                out.append(d)
        return out

    async def _candidate_educational_articles(
        self,
        org_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[tuple[Article, int | None]]:
        # Only treat articles as used if they already have a *plan* draft
        # (manual News drafts must not block AI plan fill).
        used_rows = (
            await self._session.execute(
                select(Draft.article_id, Draft.metadata_json).where(
                    Draft.organization_id == org_id,
                    Draft.article_id.is_not(None),
                )
            )
        ).all()
        used: set[uuid.UUID] = set()
        for aid, meta in used_rows:
            if aid is not None and is_plan_origin(meta if isinstance(meta, dict) else {}):
                used.add(aid)

        score_sub = (
            select(
                RelevanceScore.article_id.label("aid"),
                func.max(RelevanceScore.score).label("best_score"),
            )
            .where(RelevanceScore.organization_id == org_id)
            .group_by(RelevanceScore.article_id)
            .subquery()
        )

        stmt = (
            select(Article, score_sub.c.best_score)
            .outerjoin(score_sub, score_sub.c.aid == Article.id)
            .where(
                Article.organization_id == org_id,
                Article.status.in_(list(self._config.educational_article_statuses)),
            )
            .order_by(score_sub.c.best_score.desc().nullslast(), Article.created_at.desc())
            .limit(limit * 3)
        )
        rows = (await self._session.execute(stmt)).all()
        out: list[tuple[Article, int | None]] = []
        for article, score in rows:
            if article.id in used:
                continue
            out.append((article, int(score) if score is not None else None))
            if len(out) >= limit:
                break
        return out
