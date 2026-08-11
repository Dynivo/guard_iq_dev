"""Heuristic analyzers + semantic merge / completeness / health / recommendations."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from typing import Any

from app.modules.brand_intelligence.domain.models import (
    BrandCompletenessReport,
    BrandHealthReport,
    BrandMemoryDraft,
    BrandRecommendation,
    CanonicalBrandObject,
    CboObjectType,
    CboSourceType,
)


_CTA_PATTERNS = (
    r"\bbook a (?:call|demo)\b",
    r"\bget in touch\b",
    r"\blearn more\b",
    r"\bcontact us\b",
    r"\bschedule\b",
    r"\bdownload\b",
)
_HOOK_STARTERS = ("?", "!", "how ", "why ", "what ", "stop ", "most ", "if you")


class HeuristicOcrProvider:
    async def extract(self, storage_key: str, content_type: str | None = None) -> dict[str, Any]:
        return {
            "text": "",
            "titles": [],
            "storage_key": storage_key,
            "content_type": content_type,
            "engine": "heuristic_noop",
        }


class HeuristicVisionAnalyzer:
    async def analyze(self, storage_key: str) -> dict[str, Any]:
        """Analyze creative; when bytes are available, infer logo corner placement."""
        base: dict[str, Any] = {
            "visual_style": "corporate",
            "illustration_type": "unknown",
            "brand_colors": [],
            "logo_presence": False,
            "logo_position": None,
            "logo_confidence": 0.0,
            "layout_style": "unknown",
            "complexity": "medium",
            "storage_key": storage_key,
            "engine": "heuristic",
        }
        if not storage_key:
            return base
        try:
            from app.infrastructure.storage.factory import get_storage_provider
            from app.modules.brand_intelligence.application.logo_placement import (
                detect_logo_corner_from_bytes,
            )

            raw = get_storage_provider().get_bytes(storage_key)
            detected = detect_logo_corner_from_bytes(raw)
            base.update(detected)
            if base.get("logo_presence"):
                base["layout_style"] = f"logo_{base.get('logo_position') or 'corner'}"
        except Exception:  # noqa: BLE001
            pass
        return base


class HeuristicWritingAnalyzer:
    async def analyze(self, objects: list[CanonicalBrandObject]) -> dict[str, Any]:
        texts = [o.body_text or o.title or "" for o in objects if o.body_text or o.title]
        joined = "\n".join(texts)
        words = re.findall(r"[A-Za-z']+", joined.lower())
        sentences = [s for s in re.split(r"[.!?]+", joined) if s.strip()]
        avg_len = (sum(len(s.split()) for s in sentences) / len(sentences)) if sentences else 0
        emoji = len(re.findall(r"[\U0001F300-\U0001FAFF]", joined))
        return {
            "tone": "professional",
            "authority": "medium",
            "reading_level": "grade_10",
            "technical_depth": "medium" if any(w in words for w in ("security", "compliance", "cloud")) else "general",
            "humor": "low",
            "professionalism": "high",
            "storytelling": "medium",
            "paragraph_style": "short" if avg_len < 18 else "medium",
            "emoji_usage": "none" if emoji == 0 else "light",
            "sentence_length_avg": round(avg_len, 1),
            "post_count": len([o for o in objects if o.object_type == CboObjectType.POST]),
            "word_count": len(words),
        }


class HeuristicTopicAnalyzer:
    async def analyze(self, objects: list[CanonicalBrandObject]) -> list[dict[str, Any]]:
        bag: Counter[str] = Counter()
        keywords = (
            "security",
            "cyber",
            "compliance",
            "cloud",
            "microsoft",
            "network",
            "healthcare",
            "legal",
            "backup",
            "phishing",
            "identity",
            "voip",
            "dspt",
            "cqc",
            "gdpr",
            "mfa",
            "endpoint",
            "regulated",
            "care",
            "wifi",
            "email",
        )
        for o in objects:
            text = f"{o.title or ''} {o.body_text or ''}".lower()
            for kw in keywords:
                if kw in text:
                    bag[kw] += 1
        if not bag:
            return [{"label": "general_business", "kind": "primary", "weight": 1.0}]
        ranked = bag.most_common(8)
        out: list[dict[str, Any]] = []
        for i, (label, weight) in enumerate(ranked):
            kind = "primary" if i == 0 else ("secondary" if i < 4 else "emerging")
            out.append({"label": label, "kind": kind, "weight": float(weight)})
        return out


class HeuristicVocabularyAnalyzer:
    async def analyze(self, objects: list[CanonicalBrandObject]) -> dict[str, Any]:
        words: list[str] = []
        for o in objects:
            words.extend(re.findall(r"[A-Za-z']{4,}", (o.body_text or "").lower()))
        counts = Counter(words)
        preferred = [w for w, _ in counts.most_common(40)]
        return {
            "preferred": preferred,
            "forbidden": [],
            "phrases": [],
            "frequently_used_words": preferred[:20],
            "frequently_used_expressions": [],
        }


class HeuristicHookAnalyzer:
    async def analyze(self, objects: list[CanonicalBrandObject]) -> list[dict[str, Any]]:
        hooks: list[dict[str, Any]] = []
        for o in objects:
            if o.object_type != CboObjectType.POST:
                continue
            text = (o.body_text or o.title or "").strip()
            if not text:
                continue
            first = text.split("\n", 1)[0][:180]
            score = 1.0 if first.lower().startswith(_HOOK_STARTERS) or first.endswith(("?", "!")) else 0.4
            hooks.append({"text": first, "score": score, "source_id": str(o.id)})
        hooks.sort(key=lambda h: h["score"], reverse=True)
        return hooks[:50]


class HeuristicCtaAnalyzer:
    async def analyze(self, objects: list[CanonicalBrandObject]) -> list[dict[str, Any]]:
        ctas: list[dict[str, Any]] = []
        for o in objects:
            text = o.body_text or ""
            for pat in _CTA_PATTERNS:
                m = re.search(pat, text, flags=re.I)
                if m:
                    ctas.append({"text": m.group(0), "score": 0.8, "source_id": str(o.id)})
        return ctas[:50]


class HeuristicEngagementAnalyzer:
    async def analyze(self, objects: list[CanonicalBrandObject]) -> dict[str, Any]:
        posts = [o for o in objects if o.object_type == CboObjectType.POST]
        scored: list[tuple[float, CanonicalBrandObject]] = []
        quality_scores: list[float] = []
        with_images = 0
        for o in posts:
            eng = o.engagement or {}
            total = float(eng.get("reactions", 0) or 0) + float(eng.get("comments", 0) or 0) * 2 + float(
                eng.get("shares", 0) or 0
            ) * 3
            q = float(eng.get("quality_score") or 0)
            if q:
                quality_scores.append(q)
            if eng.get("has_image") or (o.media_refs and len(o.media_refs) > 0):
                with_images += 1
            scored.append((total, o))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1] if scored else None
        avg = sum(s for s, _ in scored) / len(scored) if scored else 0.0
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        top_quality = sorted(
            (
                {
                    "post_id": str(o.id),
                    "title": (o.title or "")[:100],
                    "quality_score": (o.engagement or {}).get("quality_score"),
                    "engagement_score": (o.engagement or {}).get("engagement_score"),
                    "has_image": (o.engagement or {}).get("has_image"),
                    "word_count": (o.engagement or {}).get("word_count"),
                }
                for o in posts
            ),
            key=lambda x: float(x.get("quality_score") or 0),
            reverse=True,
        )[:8]
        return {
            "average_engagement": avg,
            "average_quality_score": round(avg_quality, 3),
            "highest_engagement_post_id": str(best.id) if best else None,
            "best_length": len((best.body_text or "").split()) if best else None,
            "posts_with_images": with_images,
            "image_post_ratio": round(with_images / len(posts), 3) if posts else 0.0,
            "best_day": None,
            "best_time": None,
            "best_image_style": "photo" if with_images else None,
            "post_count": len(posts),
            "top_quality_posts": top_quality,
            "trends": {},
        }


class DefaultSemanticMergeEngine:
    def merge(
        self,
        objects: list[CanonicalBrandObject],
        analyses: dict[str, Any],
        org_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> BrandMemoryDraft:
        writing = analyses.get("writing") or {}
        topics = analyses.get("topics") or []
        vocab = analyses.get("vocabulary") or {}
        hooks = analyses.get("hooks") or []
        ctas = analyses.get("ctas") or []
        engagement = analyses.get("engagement") or {}
        vision_samples = analyses.get("vision") or []
        sources = {o.source_type.value for o in objects}
        from app.modules.brand_intelligence.application.logo_placement import (
            majority_logo_position,
        )

        preferred_logo = majority_logo_position(
            [v for v in vision_samples if isinstance(v, dict)]
        )
        brand_dna = {
            "industries": [t["label"] for t in topics[:3]],
            "audience": writing.get("reading_level"),
            "personality": writing.get("tone"),
            "mission": next((o.body_text for o in objects if "mission" in (o.title or "").lower()), None),
            "sources_present": sorted(sources),
            "object_count": len(objects),
        }
        visual = {
            "styles": [v.get("visual_style") for v in vision_samples if isinstance(v, dict)],
            "colors": [],
            "logo_presence": any(v.get("logo_presence") for v in vision_samples if isinstance(v, dict)),
            "preferred_logo_position": preferred_logo,
            "logo_samples": [
                {
                    "position": v.get("logo_position"),
                    "confidence": v.get("logo_confidence"),
                    "storage_key": v.get("storage_key"),
                }
                for v in vision_samples
                if isinstance(v, dict) and v.get("logo_presence")
            ][:12],
        }
        detected = {
            "topics": topics,
            "audience": writing.get("reading_level"),
            "tone": writing.get("tone"),
            "vocabulary": vocab.get("preferred", [])[:30],
            "cta": ctas[:10],
            "hooks": hooks[:10],
            "industries": brand_dna["industries"],
            "mission": brand_dna.get("mission"),
            "vision": None,
        }
        conf = min(0.95, 0.35 + 0.02 * len(objects) + (0.15 if CboSourceType.LINKEDIN.value in sources else 0))
        return BrandMemoryDraft(
            organization_id=org_id,
            brand_profile_id=profile_id,
            brand_dna=brand_dna,
            writing_dna=writing,
            visual_dna=visual,
            engagement_json=engagement,
            topics=topics,
            hooks=hooks,
            ctas=ctas,
            vocabulary=vocab,
            detected=detected,
            confidence=conf,
        )


class DefaultCompletenessEngine:
    def score(self, draft: BrandMemoryDraft, source_mix: dict[str, Any]) -> BrandCompletenessReport:
        sources = set(source_mix.get("sources") or draft.brand_dna.get("sources_present") or [])
        has_li = "linkedin" in sources
        has_web = "website" in sources
        has_logo = bool(source_mix.get("has_logo"))
        has_guidelines = bool(source_mix.get("has_guidelines"))
        writing = 0.8 if draft.writing_dna.get("word_count", 0) > 50 else 0.4
        visual = 0.7 if draft.visual_dna.get("styles") else 0.3
        topics = min(1.0, len(draft.topics) / 5)
        vocab = min(1.0, len(draft.vocabulary.get("preferred") or []) / 20)
        cta = min(1.0, len(draft.ctas) / 5) if draft.ctas else 0.2
        scores = [
            writing,
            visual,
            1.0 if has_logo else 0.2,
            topics,
            0.6,
            vocab,
            cta,
            1.0 if has_guidelines else 0.15,
            1.0 if has_web else 0.2,
            1.0 if has_li else 0.25,
            draft.confidence,
        ]
        overall = sum(scores) / len(scores)
        return BrandCompletenessReport(
            writing=writing,
            visual=visual,
            logo=1.0 if has_logo else 0.2,
            topic_coverage=topics,
            audience_coverage=0.6,
            vocabulary_coverage=vocab,
            cta_coverage=cta,
            guidelines_coverage=1.0 if has_guidelines else 0.15,
            website_coverage=1.0 if has_web else 0.2,
            linkedin_coverage=1.0 if has_li else 0.25,
            confidence=draft.confidence,
            overall_brand_score=round(overall * 100, 1),
        )


class DefaultHealthEngine:
    def evaluate(self, draft: BrandMemoryDraft, completeness: BrandCompletenessReport) -> BrandHealthReport:
        missing: list[str] = []
        actions: list[str] = []
        if completeness.logo < 0.5:
            missing.append("logo")
            actions.append("Upload your logo")
        if completeness.guidelines_coverage < 0.5:
            missing.append("brand_guidelines")
            actions.append("Upload Brand Guidelines")
        if completeness.linkedin_coverage < 0.5:
            actions.append("Connect LinkedIn and run Analyze")
        if completeness.website_coverage < 0.5:
            actions.append("Import your website")
        if completeness.cta_coverage < 0.4:
            actions.append("Improve CTA coverage with more posts or email samples")
        overall = completeness.overall_brand_score
        return BrandHealthReport(
            overall_health=overall,
            consistency=min(100.0, overall * 0.95),
            visual_consistency=completeness.visual * 100,
            writing_consistency=completeness.writing * 100,
            voice_consistency=completeness.writing * 100,
            audience_confidence=completeness.audience_coverage * 100,
            topic_diversity=completeness.topic_coverage * 100,
            asset_coverage=((completeness.logo + completeness.guidelines_coverage) / 2) * 100,
            guideline_coverage=completeness.guidelines_coverage * 100,
            missing_assets=missing,
            recommended_actions=actions,
        )


class DefaultRecommendationEngine:
    def recommend(
        self,
        draft: BrandMemoryDraft,
        completeness: BrandCompletenessReport,
        health: BrandHealthReport,
    ) -> list[BrandRecommendation]:
        recs: list[BrandRecommendation] = []
        for i, action in enumerate(health.recommended_actions):
            recs.append(
                BrandRecommendation(
                    code=f"action_{i}",
                    title=action,
                    detail=action,
                    priority=10 + i,
                )
            )
        if completeness.topic_coverage < 0.5:
            recs.append(
                BrandRecommendation(
                    code="topic_diversity",
                    title="Improve topic diversity",
                    detail="Import more posts or website content covering secondary topics.",
                    priority=40,
                )
            )
        if not recs:
            recs.append(
                BrandRecommendation(
                    code="sync_latest",
                    title="Sync latest posts",
                    detail="Keep Brand Memory fresh with Sync Latest Posts.",
                    priority=80,
                )
            )
        return recs


def fingerprint_text(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8"))
    return h.hexdigest()[:40]
