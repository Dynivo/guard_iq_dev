"""Visual strategy engine — plans extended VisualDesignSpec for Gemini modes."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.core.logging import get_logger
from app.modules.image.application.config_loader import load_yaml
from app.modules.image.application.design_spec_builder import (
    _best_subheadline,
    _extract_bullets,
    _extract_fact_phrases,
    _extract_stats,
    build_design_spec,
    resolve_motifs,
)
from app.modules.image.domain.design_spec import (
    VisualDesignSpec,
    VisualHierarchy,
    VisualRelationship,
    VisualStatistic,
    VisualStory,
)

logger = get_logger(__name__)

_COMPARE_RE = re.compile(
    r"\b(vs\.?|versus|compared to|before|after|instead of|rather than)\b", re.I
)
_RISK_RE = re.compile(
    r"\b(risk|threat|breach|attack|vulnerab|malware|ransomware|exploit)\b", re.I
)
_HUB_RE = re.compile(
    r"\b(ecosystem|platform|framework|central|hub|across|connected|integrate)\b", re.I
)
_STEP_RE = re.compile(
    r"(?m)^\s*(?:\d+[\.\)]\s+|[-•]\s+)(.+)$|"
    r"\b(step\s+\d+|first,?|second,?|third,?|finally|then)\b",
    re.I,
)


@lru_cache(maxsize=1)
def _strategy_cfg() -> dict[str, Any]:
    return load_yaml("visual_strategy.yaml")


@lru_cache(maxsize=1)
def _archetypes_cfg() -> dict[str, Any]:
    return load_yaml("archetypes.yaml")


def _format_dims(fmt: str) -> tuple[int, int, str]:
    cfg = _strategy_cfg()
    formats = cfg.get("formats") or {}
    entry = formats.get(fmt) or formats.get("linkedin_portrait") or {}
    return (
        int(entry.get("width") or 1080),
        int(entry.get("height") or 1350),
        str(entry.get("aspect_ratio") or "4:5"),
    )


def _normalize_format(raw: str | None) -> str:
    v = (raw or "").strip().lower()
    if v in {"square", "1:1", "linkedin_square"}:
        return "linkedin_square"
    if v in {"portrait", "4:5", "linkedin_portrait", ""}:
        return "linkedin_portrait"
    if v in {"linkedin_square", "linkedin_portrait"}:
        return v
    return "linkedin_portrait"


def _score_archetypes(
    *,
    content_type: str,
    text: str,
    stats: list[str],
    bullets: list[str],
    visual_style: str | None,
) -> str:
    cfg = _strategy_cfg()
    weights: dict[str, float] = {}
    ct = (content_type or "educational").strip().lower()
    for arch, w in ((cfg.get("content_type_weights") or {}).get(ct) or {}).items():
        weights[str(arch)] = float(w)

    boosts = cfg.get("signal_boosts") or {}
    if stats:
        for arch, w in (boosts.get("has_primary_stat") or {}).items():
            weights[str(arch)] = weights.get(str(arch), 0.0) + float(w)
    if bullets or _STEP_RE.search(text or ""):
        for arch, w in (boosts.get("has_steps") or {}).items():
            weights[str(arch)] = weights.get(str(arch), 0.0) + float(w)
    if _COMPARE_RE.search(text or ""):
        for arch, w in (boosts.get("has_comparison_language") or {}).items():
            weights[str(arch)] = weights.get(str(arch), 0.0) + float(w)
    if _RISK_RE.search(text or ""):
        for arch, w in (boosts.get("has_risk_language") or {}).items():
            weights[str(arch)] = weights.get(str(arch), 0.0) + float(w)
    if _HUB_RE.search(text or ""):
        for arch, w in (boosts.get("has_hub_language") or {}).items():
            weights[str(arch)] = weights.get(str(arch), 0.0) + float(w)

    style = (visual_style or "auto").strip().lower()
    aliases = (_archetypes_cfg().get("style_aliases") or {})
    alias = aliases.get(style)
    if alias:
        weights[str(alias)] = weights.get(str(alias), 0.0) + 5.0

    if not weights:
        return str(_archetypes_cfg().get("default") or "statistic_threat_alert")
    return max(weights.items(), key=lambda kv: kv[1])[0]


def _build_statistics(
    *,
    primary_stat: str,
    supporting: tuple[str, ...],
    fact_phrases: list[str],
    max_supporting: int,
    max_context: int,
) -> tuple[VisualStatistic, ...]:
    out: list[VisualStatistic] = []
    if primary_stat:
        label = ""
        for fp in fact_phrases:
            if primary_stat.lower() in fp.lower() or fp.lower().startswith(
                re.sub(r"[^\d.%x+]", "", primary_stat.lower())[:4]
            ):
                label = fp
                break
        out.append(VisualStatistic(value=primary_stat, label=label or primary_stat, role="hero"))
    for s in supporting[:max_supporting]:
        out.append(VisualStatistic(value=s, label=s, role="supporting"))
    # Context from leftover fact phrases (not duplicating hero/supporting)
    used = {x.value.lower() for x in out} | {x.label.lower() for x in out if x.label}
    ctx = 0
    for fp in fact_phrases:
        if fp.lower() in used or any(fp.lower() in u for u in used):
            continue
        out.append(VisualStatistic(value=fp, label=fp, role="context"))
        ctx += 1
        if ctx >= max_context:
            break
    return tuple(out)


def _build_relationships(
    *,
    archetype: str,
    content_blocks: tuple[str, ...],
    motifs: tuple[str, ...],
    headline: str,
    max_rels: int,
) -> tuple[VisualRelationship, ...]:
    hub = (headline or "Core insight").strip()[:80] or "Core insight"
    nodes = list(content_blocks) or [m.replace("_", " ").title() for m in motifs[:4]]
    if not nodes:
        return ()
    rels: list[VisualRelationship] = []
    if archetype in {"central_hub", "risk_map", "threat_risk_map"}:
        for node in nodes[:max_rels]:
            rels.append(VisualRelationship(from_node=hub, to_node=node[:80], label="relates"))
    elif archetype in {"process_flow", "explainer_infographic", "timeline"}:
        seq = [hub, *nodes]
        for i in range(min(len(seq) - 1, max_rels)):
            rels.append(
                VisualRelationship(
                    from_node=seq[i][:80],
                    to_node=seq[i + 1][:80],
                    label="next" if archetype != "timeline" else "then",
                )
            )
    elif archetype == "comparison" and len(nodes) >= 2:
        rels.append(
            VisualRelationship(from_node=nodes[0][:80], to_node=nodes[1][:80], label="versus")
        )
    return tuple(rels)


def _factual_constraints(spec: VisualDesignSpec) -> tuple[str, ...]:
    items: list[str] = []
    for field in (spec.headline, spec.subheadline, spec.primary_stat, spec.cta):
        if field and str(field).strip():
            items.append(str(field).strip())
    for s in spec.supporting_stats:
        if s.strip():
            items.append(s.strip())
    for b in spec.content_blocks:
        if b.strip():
            items.append(b.strip())
    for st in spec.statistics:
        if st.value.strip():
            items.append(st.value.strip())
        if st.label.strip() and st.label.strip() not in items:
            items.append(st.label.strip())
    # Dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        key = x.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    max_n = int((_strategy_cfg().get("defaults") or {}).get("max_factual_constraints") or 12)
    return tuple(out[:max_n])


class VisualStrategyEngine:
    """Plans a VisualDesignSpec enriched for Gemini infographic generation."""

    def plan(
        self,
        draft: dict[str, Any],
        brand: dict[str, Any] | None = None,
        *,
        source_excerpt: str | None = None,
        visual_style: str | None = "auto",
        quality: str | None = "premium",
        image_format: str | None = "portrait",
        include_logo: bool | None = None,
        logo_position: str | None = None,
        logo_size: str | None = None,
        variant_index: int = 0,
        creative_mode: str = "gemini_infographic",
    ) -> VisualDesignSpec:
        brand = brand or {}
        cfg = _strategy_cfg()
        defaults = cfg.get("defaults") or {}
        mode = (creative_mode or "gemini_infographic").lower()
        mode_over = (cfg.get("creative_mode_overrides") or {}).get(mode) or {}

        hook = str(draft.get("hook") or "")
        body = str(draft.get("body") or draft.get("edited_text") or draft.get("generated_text") or "")
        cta = str(draft.get("cta") or "")
        content_type = str(draft.get("content_type") or "educational")
        source = str(draft.get("source") or "")
        text = f"{hook}\n{body}\n{source_excerpt or ''}"

        stats = _extract_stats(text)
        bullets = _extract_bullets(body)
        topic_id, motifs = resolve_motifs(text)
        preferred = _score_archetypes(
            content_type=content_type,
            text=text,
            stats=stats,
            bullets=bullets,
            visual_style=visual_style,
        )

        base = build_design_spec(
            hook=hook,
            body=body,
            cta=cta,
            title=hook,
            content_type=content_type,
            brand=brand,
            source=source,
            visual_style=visual_style,
            include_logo=include_logo,
            logo_position=logo_position,
            logo_size=logo_size,
            variant_index=variant_index,
            forced_archetype=preferred if (visual_style or "auto").lower() in {"auto", ""} else None,
        )

        fmt = _normalize_format(image_format or defaults.get("format"))
        width, height, aspect = _format_dims(fmt)

        arch_meta = (_archetypes_cfg().get("archetypes") or {}).get(base.design_archetype) or {}
        density = str(
            mode_over.get("density")
            or arch_meta.get("density")
            or defaults.get("density")
            or "medium"
        )
        complexity = str(
            mode_over.get("complexity")
            or arch_meta.get("complexity")
            or defaults.get("complexity")
            or "moderate"
        )
        coverage = str(
            mode_over.get("coverage_hint")
            or arch_meta.get("coverage")
            or defaults.get("coverage_hint")
            or "filled_infographic"
        )
        dens_cfg = (cfg.get("density_thresholds") or {}).get(density) or {}
        max_sup = int(dens_cfg.get("max_supporting_stats") or defaults.get("max_supporting_stats") or 2)
        max_ctx = int(defaults.get("max_context_stats") or 2)
        max_rels = int(defaults.get("max_relationships") or 5)
        max_blocks = int(dens_cfg.get("max_content_blocks") or 3)

        fact_phrases = _extract_fact_phrases(text, limit=6)
        if not base.subheadline:
            patched = base.to_dict()
            patched["subheadline"] = _best_subheadline(body, hook=hook)
            base = VisualDesignSpec.from_dict(patched)

        # Poster dedupe may clear primary_stat when it overlaps the subheadline.
        # Gemini infographics still need a hero metric — restore from facts/stats.
        primary_stat = base.primary_stat
        supporting = base.supporting_stats
        if not primary_stat:
            if fact_phrases:
                primary_stat = fact_phrases[0]
            elif stats:
                primary_stat = stats[0]
            if primary_stat and primary_stat in supporting:
                supporting = tuple(s for s in supporting if s != primary_stat)

        statistics = _build_statistics(
            primary_stat=primary_stat,
            supporting=supporting,
            fact_phrases=fact_phrases,
            max_supporting=max_sup,
            max_context=max_ctx,
        )
        content_blocks = tuple(list(base.content_blocks)[:max_blocks])
        relationships = _build_relationships(
            archetype=base.design_archetype,
            content_blocks=content_blocks,
            motifs=base.visual_motifs or motifs,
            headline=base.headline,
            max_rels=max_rels,
        )

        narrative = base.subheadline or base.headline
        metaphor = (base.visual_concept or " ".join(base.visual_motifs[:3])).strip()
        takeaway = (base.cta_body or base.cta or "").strip()
        story = VisualStory(
            narrative=narrative[:280],
            metaphor=metaphor[:180],
            viewer_takeaway=takeaway[:180],
        )
        hierarchy = VisualHierarchy(
            primary_focus="headline" if not base.primary_stat else "hero_stat",
            secondary_focus="supporting_stats" if statistics else "content_blocks",
            density=density,
            complexity=complexity,
            coverage_hint=coverage,
        )

        layout = base.layout
        layout = type(layout)(
            type=str(arch_meta.get("layout_type") or layout.type),
            columns=layout.columns,
            density=density,
            width=width,
            height=height,
        )

        logo = base.logo
        if arch_meta.get("logo_placement") and not logo_position:
            logo = type(logo)(
                enabled=logo.enabled,
                position=str(arch_meta.get("logo_placement") or logo.position),
                size=logo.size,
            )

        instruction_bits = [
            f"Create a professional LinkedIn {fmt.replace('_', ' ')} infographic.",
            f"Archetype: {base.design_archetype}.",
            f"Theme: {base.brand_variant}. Density: {density}. Coverage: {coverage}.",
            f"Aspect ratio {aspect} ({width}x{height}).",
        ]
        if topic_id:
            instruction_bits.append(f"Topic motif: {topic_id}.")

        enriched = VisualDesignSpec(
            format=fmt,
            design_archetype=base.design_archetype,
            headline=base.headline,
            subheadline=base.subheadline,
            primary_stat=primary_stat,
            supporting_stats=supporting[:max_sup],
            visual_concept=base.visual_concept,
            visual_elements=base.visual_elements,
            content_blocks=content_blocks,
            cta=base.cta,
            cta_body=base.cta_body,
            source=base.source,
            category_label=base.category_label,
            brand_name=base.brand_name,
            tagline=base.tagline,
            logo=logo,
            brand=base.brand,
            layout=layout,
            typography_template=base.typography_template,
            brand_variant=base.brand_variant,
            visual_motifs=base.visual_motifs,
            metadata={
                **dict(base.metadata),
                "quality_tier": (quality or "premium").lower(),
                "aspect_ratio": aspect,
                "creative_mode": mode,
                "strategy_topic": topic_id,
            },
            statistics=statistics,
            relationships=relationships,
            story=story,
            hierarchy=hierarchy,
            factual_constraints=(),
            image_generation_instruction=" ".join(instruction_bits),
        )
        facts = _factual_constraints(enriched)
        enriched = VisualDesignSpec.from_dict(
            {**enriched.to_dict(), "factual_constraints": list(facts)}
        )

        logger.info(
            "visual_strategy_planned archetype=%s format=%s density=%s stats=%s rels=%s",
            enriched.design_archetype,
            enriched.format,
            density,
            len(enriched.statistics),
            len(enriched.relationships),
        )
        return enriched
