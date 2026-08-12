"""Derive a concrete visual subject from LinkedIn post copy.

Client house style: light educational infographics with short labels (2–4 words),
charts/nodes/process — not dark neon “person + floating icons” cards.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.core.logging import get_logger
from app.modules.image.application.config_loader import load_yaml
from app.modules.image.application.visual_planning import (
    format_planning_prompt_clause,
    plan_visual,
)

logger = get_logger(__name__)

# Phrases that signal “this anecdote is NOT the visual subject”
_NOISE_EXAMPLE = re.compile(
    r"\b(?:while\s+significant|doesn't\s+directly\s+affect|does\s+not\s+directly|"
    r"in\s+its\s+own\s+context|filtering\s+out\s+the\s+noise|"
    r"what\s+does\s+matter|genuinely\s+matters)\b",
    re.I,
)
_FOREIGN_NEWS = re.compile(
    r"\b(?:texas|california|florida|us\s+court|u\.s\.|united\s+states|"
    r"gun\s+ban|state\s+fair|appeals\s+court)\b",
    re.I,
)


def _clean(text: str, limit: int = 220) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = re.sub(r"#\w+", "", t).strip()
    return t[:limit].strip(" ,.-")


@lru_cache(maxsize=1)
def _layouts_cfg() -> dict[str, Any]:
    return load_yaml("content_layouts.yaml")


def _mode_spec(mode: str) -> dict[str, Any]:
    modes = (_layouts_cfg().get("modes") or {}) if _layouts_cfg() else {}
    spec = modes.get(mode) or modes.get("hero_with_accents") or {}
    return dict(spec) if isinstance(spec, dict) else {}


# Trailing words that make a hard word-count cutoff read as mid-sentence
# (e.g. "Ensure your systems are" / "Train your team to") rather than a label.
_TRAILING_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "nor", "for", "so", "yet",
    "of", "in", "on", "at", "by", "to", "with", "from", "into", "onto",
    "about", "over", "under", "per", "via", "as", "than", "then", "if",
    "that", "this", "these", "those", "is", "are", "was", "were", "be",
    "been", "being", "your", "our", "their", "its", "his", "her", "my",
}


def _short_label(text: str, max_words: int = 4) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9%-]+", text or "") if w][:max_words]
    while len(words) > 1 and words[-1].lower() in _TRAILING_STOPWORDS:
        words.pop()
    return " ".join(words)


def _curated_legal_labels() -> list[str]:
    raw = _layouts_cfg().get("legal_labels") or [
        "Legal landscape",
        "Due diligence",
        "Key providers",
    ]
    out: list[str] = []
    for item in raw:
        s = str(item).strip()
        if s and s.lower() not in {x.lower() for x in out}:
            out.append(s)
    return out[:3]


async def _author_bullet_labels(
    bullets: list[str], *, orchestrator: Any, organization_id: str | None
) -> list[str] | None:
    """Ask the AI orchestrator for genuine short labels (not truncated sentences).

    Best-effort: returns None on any failure so the caller falls back to the
    deterministic word-cap extraction. Uses the existing `image_prompting`
    capability (cheap, cacheable) — no new provider/routing config needed.
    """
    if orchestrator is None or not bullets:
        return None
    items = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(bullets[:3]))
    prompt = (
        "You write short labels for boxes/icons in a LinkedIn infographic.\n"
        "For each numbered action item below, write a 2-4 word label that "
        "captures its actual point as a short noun or imperative phrase "
        "(e.g. 'Ensure your systems are updated' -> 'System updates', "
        "'Train your team to spot potential threats' -> 'Team training'). "
        "Never truncate mid-sentence; the label must stand alone and make sense.\n\n"
        f"{items}\n\n"
        'Respond with ONLY a JSON array of strings, one label per item, same order, '
        'e.g. ["System updates", "Team training"].'
    )
    try:
        result = await orchestrator.complete(
            "image_prompting",
            prompt,
            organization_id=organization_id,
            response_format="json",
            max_tokens=200,
        )
        data = json.loads(result.text)
        if not isinstance(data, list):
            return None
        out: list[str] = []
        for item in data:
            lab = _clean(str(item), 40).strip(" .")
            if lab and len(lab.split()) <= 5 and lab.lower() not in {x.lower() for x in out}:
                out.append(lab)
        return out or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI label authoring failed, using deterministic fallback: %s", exc)
        return None


async def _extract_short_labels(
    *,
    hook: str,
    body: str,
    stats: list[str],
    visual_mode: str = "",
    orchestrator: Any = None,
    organization_id: str | None = None,
) -> list[str]:
    """2–4 word labels for nodes/charts — never full sentences."""
    # Legal / due-diligence: fixed whitelist only (avoids clutter + misspellings).
    if visual_mode == "legal_context":
        return _curated_legal_labels()
    # Noise-filter / funnel: curated UK-practice outcomes (not foreign headline text).
    if visual_mode == "signal_filter":
        curated = _layouts_cfg().get("signal_filter_labels") or [
            "Compliance risk",
            "UK regulation",
        ]
        return [str(x).strip() for x in curated if str(x).strip()][:3]

    labels: list[str] = []
    for s in stats[:1]:
        labels.append(_short_label(f"{s} found", 3) if s.isdigit() else _short_label(s, 3))

    bullets = re.findall(r"(?:^|\n)\s*(?:[-•*]|\d+[.)])\s+(.+)", body or "")
    ai_labels = await _author_bullet_labels(
        bullets, orchestrator=orchestrator, organization_id=organization_id
    )
    for lab in ai_labels if ai_labels is not None else [_short_label(b, 4) for b in bullets]:
        if lab and lab.lower() not in {x.lower() for x in labels}:
            labels.append(lab)
        if len(labels) >= 3:
            break

    lower = f"{hook} {body}".lower()
    fallbacks = [
        ("malware", "Hidden malware"),
        ("threat", "Hidden threats"),
        ("compliance", "Compliance risk"),
        ("access control", "Access control"),
        ("azure", "Cloud exposure"),
        ("breach", "Breach risk"),
        ("detect", "AI detection"),
        ("cve-", "Patch now"),
    ]
    for key, lab in fallbacks:
        if key in lower and lab.lower() not in {x.lower() for x in labels}:
            labels.append(lab)
        if len(labels) >= 3:
            break

    if not labels and hook:
        labels.append(_short_label(hook, 4))
    return labels[:3]


def _icon_themes_from_text(text: str, *, content_type: str = "") -> list[str]:
    """Map post language to abstract icon themes."""
    lower = (text or "").lower()
    themes: list[str] = []

    def add(name: str) -> None:
        if name not in themes:
            themes.append(name)

    if any(k in lower for k in ("cqc", "dsp", "care home", "care practice", "healthcare", "patient")):
        add("uk_care_compliance")
    if any(k in lower for k in ("sra", "legal", "solicitor", "law firm", "accountanc", "fca")):
        add("uk_professional_services")
    if any(k in lower for k in ("filter", "noise", "relevant", "headline", "sifting", "deluge")):
        add("signal_vs_noise")
        add("focused_target")
    if any(k in lower for k in ("cyber", "security", "mfa", "phish", "ransomware", "breach", "malware")):
        add("cyber_shield")
    if any(k in lower for k in ("gdpr", "data", "compliance", "regulat", "audit")):
        add("compliance_clipboard")
    if any(k in lower for k in ("microsoft", "365", "m365", "email", "bec", "invoice", "azure")):
        add("secure_cloud")
    if any(k in lower for k in ("lawsuit", "class action", "lead plaintiff", "securities")):
        add("due_diligence")
    if content_type == "success_story":
        add("growth_chart")
        add("team_win")
    elif content_type == "personal_achievement":
        add("milestone_badge")
    elif content_type == "educational" or not themes:
        add("education_insight")

    return themes[:5] or ["professional_insight", "uk_business"]


def _extract_body_cues(body: str, hook: str = "") -> dict[str, Any]:
    """Heuristic cues from body for visual layout."""
    text = body or ""
    lower = f"{hook} {text}".lower()
    bullets = re.findall(r"(?:^|\n)\s*(?:[-•*]|\d+[.)])\s+(.+)", text)
    bullets = [_clean(b, 80) for b in bullets if _clean(b, 80)][:6]

    # Include plain integers (e.g. "34 instances") — not only % / $ stats.
    numbers = re.findall(
        r"\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*(?:million|billion|k\b)|\$\d+|"
        r"\b(?<!CVE-)\d{1,3}\b",
        text,
        flags=re.I,
    )
    # Drop year-like 20xx and CVE-ish noise
    stats: list[str] = []
    for n in numbers:
        raw = n.strip()
        if re.fullmatch(r"20\d{2}", raw):
            continue
        if raw not in stats:
            stats.append(raw)
        if len(stats) >= 4:
            break

    steps = any(
        k in lower
        for k in ("step 1", "first,", "second,", "third,", "1.", "2.", "3.")
    ) or len(bullets) >= 3
    comparison = any(
        k in lower for k in (" vs ", "versus", "compared to", "instead of", "rather than")
    )
    triad = any(
        k in lower
        for k in ("three ", "3 pillars", "triad", "confidentiality, integrity", "cia triad")
    )
    process = any(
        k in lower
        for k in ("workflow", "pipeline", "lifecycle", "then ", "→", "leads to", "results in")
    )
    filtering = bool(_NOISE_EXAMPLE.search(text)) or any(
        k in lower for k in ("filtering out", "what does matter", "genuinely matters", "noise")
    )
    malware_stat = any(k in lower for k in ("malware", "threat", "ransomware")) and bool(stats)
    access_vuln = any(
        k in lower
        for k in ("cve-", "vulnerability", "access control", "azure", "api management", "privilege")
    )
    legal_story = any(
        k in lower
        for k in ("lawsuit", "class action", "lead plaintiff", "securities", "rosen law")
    )

    if filtering:
        mode = "signal_filter"
    elif malware_stat or (stats and any(k in lower for k in ("malware", "threat", "instance"))):
        mode = "big_stat"
    elif access_vuln:
        mode = "access_control"
    elif legal_story:
        mode = "legal_context"
    elif triad or (len(bullets) == 3 and not stats):
        mode = "connected_nodes"
    elif stats and (comparison or "chart" in lower or "rate" in lower or "%" in text):
        mode = "big_stat"
    elif steps or len(bullets) >= 3:
        mode = "process_pictogram"
    elif comparison:
        mode = "comparison"
    elif process:
        mode = "flow_nodes"
    else:
        # Educational default: connected insight nodes — never floating-icon portrait
        mode = "connected_nodes" if any(
            k in lower for k in ("cyber", "security", "compliance", "practice")
        ) else "flow_nodes"

    spec = _mode_spec(mode)
    visual_elements = str(spec.get("visual_elements") or "").strip()
    charts = tuple(spec.get("charts") or ())
    graphs = tuple(spec.get("graphs") or ())
    surface = str(_layouts_cfg().get("surface") or "")
    ban = str(_layouts_cfg().get("ban_default_hero") or "")
    if surface:
        visual_elements = f"{visual_elements}. Surface: {surface}"
    if ban:
        visual_elements = f"{visual_elements}. {ban}"

    return {
        "visual_mode": mode,
        "visual_elements": visual_elements,
        "charts": charts,
        "graphs": graphs,
        "stat_hints": stats[:4],
        "filtering": filtering,
    }


async def _author_visual_concept(
    *,
    hook: str,
    body: str,
    orchestrator: Any,
    organization_id: str | None,
) -> dict[str, Any] | None:
    """Ask the AI for a specific visual concept grounded in this exact post,
    instead of the generic "cybersecurity education infographic" template.

    Best-effort: returns None on any failure (including no orchestrator) so
    the caller falls back to the deterministic template unchanged — same
    safety-net pattern as ``_author_bullet_labels``.
    """
    if orchestrator is None or not (hook or body):
        return None
    prompt = (
        "You are planning a LinkedIn infographic image for a security-led UK "
        "IT/cybersecurity MSP. Given this post, describe a SPECIFIC visual "
        "concept — not a generic security-clipart scene. Avoid default padlocks, "
        "hooded hackers, or vague 'threat' icons unless that is literally the "
        "post's main point; ground the concept in the actual mechanism or "
        "objects the post describes.\n\n"
        f"HOOK: {hook}\n"
        f"BODY: {(body or '')[:1500]}\n\n"
        "Respond with ONLY JSON:\n"
        '{"subject": "one short phrase naming the specific topic", '
        '"must_depict": "1-2 sentences describing a specific scene/diagram '
        "that visually represents this post's actual point, referencing the "
        'real mechanism or objects it mentions", '
        '"labels": ["2-4 word label", "up to 3 total"]}'
    )
    try:
        result = await orchestrator.complete(
            "image_prompting",
            prompt,
            organization_id=organization_id,
            response_format="json",
            max_tokens=300,
        )
        data = json.loads(result.text)
        subject = _clean(str(data.get("subject") or ""), 160)
        must_depict = _clean(str(data.get("must_depict") or ""), 400)
        if not subject or not must_depict:
            return None
        labels: list[str] = []
        for item in data.get("labels") or []:
            lab = _clean(str(item), 40).strip(" .")
            if lab and len(lab.split()) <= 5 and lab.lower() not in {x.lower() for x in labels}:
                labels.append(lab)
        return {"subject": subject, "must_depict": must_depict, "labels": labels[:3]}
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI visual concept authoring failed, using template fallback: %s", exc)
        return None


async def build_content_subject(
    *,
    hook: str = "",
    body: str = "",
    cta: str = "",
    title: str = "",
    article_title: str = "",
    content_type: str = "",
    orchestrator: Any = None,
    organization_id: str | None = None,
) -> dict[str, str]:
    """Return prompt fragments grounded in the post text (hook + theme)."""
    blob = " ".join(p for p in (hook, body, cta, title, article_title) if p)
    lower = blob.lower()
    hook_short = _clean(hook or title or article_title, 160)
    cues = _extract_body_cues(body, hook=hook)
    icon_themes = _icon_themes_from_text(blob, content_type=content_type or "")
    ideas = ", ".join(icon_themes)
    stats = ", ".join(cues["stat_hints"][:3]) if cues["stat_hints"] else ""
    labels = await _extract_short_labels(
        hook=hook,
        body=body,
        stats=list(cues["stat_hints"]),
        visual_mode=str(cues.get("visual_mode") or ""),
        orchestrator=orchestrator,
        organization_id=organization_id,
    )
    labels_s = "; ".join(labels)
    ctype = (content_type or "educational").strip().lower()
    surface = str(_layouts_cfg().get("surface") or "light off-white consulting background")
    ban_hero = str(_layouts_cfg().get("ban_default_hero") or "")
    label_rules = str(_layouts_cfg().get("label_rules") or "")

    palette_note = (
        "STRICT client Brand Kit colour palette (injected hexes), "
        f"{surface}"
    )

    if cues.get("filtering") or (
        _FOREIGN_NEWS.search(body or "") and _NOISE_EXAMPLE.search(body or "")
    ):
        must = (
            "META MESSAGE is filtering news noise for UK regulated practices — "
            "DO NOT illustrate US gun laws, Texas courts, shootings, or foreign headlines. "
            "Show a premium decision-funnel visual story: many muted grey news cards enter "
            "a large modern funnel; inside the funnel only two highlighted short-label cards "
            f"({labels_s or 'Compliance risk; UK regulation'}); bottom has a minimal target/bullseye. "
            "Flat vector, Stripe/Cloudflare-grade whitespace, no humans, no robots. "
            f"{palette_note}. {ban_hero}. NO LinkedIn logo"
        )
        style_note = "signal_vs_noise"
    elif any(
        k in lower
        for k in (
            "senior living",
            "care home",
            "care community",
            "aged care",
            "assisted living",
            "ltc ",
            "nursing",
        )
    ):
        must = (
            "senior care investment educational graphic with growth chart and short labels, "
            f"{palette_note}. {ban_hero}. NOT padlock spam unless the post is about security"
        )
        style_note = "care_sector_investment"
    elif any(k in lower for k in ("bec", "invoice", "lookalike", "fake email")) or (
        "phishing" in lower and "phishing-resistant" not in lower and "phishing resistant" not in lower
    ):
        must = (
            "educational BEC / fake invoice graphic: two side-by-side email mock cards "
            "with short panel labels (e.g. Real / Fake), magnifying glass cue, "
            f"{palette_note}. {ban_hero}. NO LinkedIn logo"
        )
        style_note = "bec_education"
    elif any(k in lower for k in ("cia triad", "confidentiality", "integrity", "availability")):
        must = (
            "CIA triad educational graphic: three connected circular nodes with short labels "
            f"Confidentiality / Integrity / Availability, {palette_note}. {ban_hero}"
        )
        style_note = "cia_framework"
    elif cues["visual_mode"] == "big_stat":
        must = (
            "BIG STAT educational LinkedIn infographic (no full-sentence headline in the art). "
            f"Hero numeral {stats or 'key number'} with a tiny short label only, "
            f"plus 3 connected circular nodes labelled: {labels_s or ideas}. "
            f"Theme: {_short_label(hook_short, 6) or 'practice software risk'}. "
            f"Layout: {cues['visual_elements']}. {palette_note}. {ban_hero}. "
            f"{label_rules} Leave empty margin at top/bottom for optional overlay."
        )
        style_note = "big_stat_education"
    elif cues["visual_mode"] == "access_control":
        must = (
            f"Access-control / vulnerability education infographic for: '{hook_short}'. "
            f"Diagram of improper access → network exposure → compliance risk with short labels "
            f"({labels_s or 'Authorize; Expose; Breach risk'}). "
            f"{palette_note}. {ban_hero}. {label_rules}"
        )
        style_note = "access_control_education"
    elif cues["visual_mode"] == "legal_context":
        must = (
            "PREMIUM due-diligence educational LinkedIn creative for UK practice managers "
            "(this post is NOT about IT hacking or cybersecurity tools). "
            "Use EXACTLY three equal horizontal cards with EXACT labels only: "
            f"{labels_s or 'Legal landscape; Due diligence; Key providers'}. "
            "Card 1 scales icon, Card 2 document checklist icon, Card 3 building/handshake icon. "
            "Bright off-white #F4F7F5, navy/teal accents, generous white space, "
            "single clean composition — NOT a cluttered mind-map, NOT duplicate labels, "
            "NOT Vendor/Provider/Reseller/Distributor synonym spam, NOT misspelled words, "
            f"NOT angry courtroom portrait. {palette_note}. {ban_hero}. {label_rules}"
        )
        style_note = "legal_due_diligence"
    elif any(
        k in lower
        for k in (
            "ransomware",
            "malware",
            "mfa",
            "phishing",
            "cyber",
            "breach",
            "password",
            "ai agent",
            "security threat",
            "authentication",
            "vulnerability",
        )
    ):
        concept = await _author_visual_concept(
            hook=hook, body=body, orchestrator=orchestrator, organization_id=organization_id
        )
        if concept and concept["labels"]:
            labels_s = "; ".join(concept["labels"])
        if concept:
            must = (
                f"{concept['must_depict']} {palette_note}. {ban_hero}. {label_rules}. "
                "NO LinkedIn logo"
            )
        else:
            must = (
                "cybersecurity education infographic matching THIS post body — "
                f"layout ({cues['visual_elements']}), short labels: {labels_s or ideas}. "
                f"{palette_note}. {ban_hero}. {label_rules}. NO LinkedIn logo"
            )
        style_note = "cyber_education"
    elif ctype == "success_story":
        must = (
            f"success-story educational graphic for '{hook_short or 'client outcome'}' "
            f"with outcome nodes/labels ({labels_s or ideas}). {palette_note}. {ban_hero}"
        )
        style_note = "success_story"
    else:
        concept = await _author_visual_concept(
            hook=hook, body=body, orchestrator=orchestrator, organization_id=organization_id
        )
        if concept and concept["labels"]:
            labels_s = "; ".join(concept["labels"])
        if concept:
            must = f"{concept['must_depict']} {palette_note}. {ban_hero}. {label_rules}"
        else:
            must = (
                f"Educational LinkedIn infographic for: '{hook_short or 'professional insight'}'. "
                f"Visual system: {cues['visual_elements']}. Short labels: {labels_s or ideas}. "
                f"{palette_note}. {ban_hero}. {label_rules}"
            )
        style_note = "content_grounded"

    subject = hook_short or "LinkedIn educational post"
    if cues.get("filtering"):
        subject = _clean(
            hook_short or "Filtering global news for what UK practices truly need",
            180,
        )

    return {
        "content_subject": subject,
        "must_depict": must,
        "style_note": style_note,
        "post_summary": _clean(blob, 320),
        "visual_mode": cues["visual_mode"],
        "visual_elements": cues["visual_elements"],
        "body_key_ideas": labels_s or ideas,
        "short_labels": labels_s,
        "icon_themes": ideas,
        "stat_hints": stats,
        "charts": ",".join(cues["charts"]),
        "graphs": ",".join(cues["graphs"]),
        "content_type": ctype,
    }


async def inject_content_into_brief(
    visual_brief: dict[str, Any] | None,
    *,
    hook: str = "",
    body: str = "",
    cta: str = "",
    title: str = "",
    article_title: str = "",
    content_type: str = "",
    brand_palette: list[str] | tuple[str, ...] | None = None,
    brand: dict[str, Any] | None = None,
    linkedin_image_type: str = "single_post",
    variant_index: int = 0,
    orchestrator: Any = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """Merge content-grounded scene into an existing visual brief dict."""
    subject = await build_content_subject(
        hook=hook,
        body=body,
        cta=cta,
        title=title,
        article_title=article_title,
        content_type=content_type,
        orchestrator=orchestrator,
        organization_id=organization_id,
    )
    brand_ctx = dict(brand or {})
    if brand_palette and not brand_ctx.get("primary_color"):
        pals = list(brand_palette)
        if pals:
            brand_ctx.setdefault("primary_color", pals[0])
        if len(pals) > 1:
            brand_ctx.setdefault("secondary_color", pals[1])
        if len(pals) > 2:
            brand_ctx.setdefault("accent_color", pals[2])

    plan = plan_visual(
        hook=hook,
        body=body,
        cta=cta,
        content_type=content_type,
        legacy_visual_mode=str(subject.get("visual_mode") or ""),
        short_labels=str(subject.get("short_labels") or ""),
        brand=brand_ctx,
        linkedin_image_type=linkedin_image_type,
        variant_index=variant_index,
    )
    planning_clause = format_planning_prompt_clause(plan)
    pattern = plan.get("pattern") or {}
    pattern_icons = list(pattern.get("icon_suggestions") or [])

    brief = dict(visual_brief or {})
    label_rules = str(_layouts_cfg().get("label_rules") or "")
    ban_hero = str(_layouts_cfg().get("ban_default_hero") or "")
    scene = (
        f"Create a premium LinkedIn infographic with a clean editorial style. "
        f"{planning_clause} "
        f"MUST DEPICT: {subject['must_depict']}. "
        f"Post focus: {subject['content_subject']}. "
        f"Visual system: {subject['visual_elements']}. "
        f"Short labels to include: {subject.get('short_labels') or subject['body_key_ideas']}. "
        f"{label_rules} {ban_hero}"
    )
    brief["scene"] = scene
    brief["scene_hint"] = scene
    brief["focal_point"] = subject["content_subject"][:48] or "content focal subject"
    # Prefer educational infographic for almost all grounded posts
    if subject["visual_mode"] != "hero_with_accents":
        brief["illustration_style"] = "educational_infographic"
    else:
        brief["illustration_style"] = brief.get("illustration_style") or "branded_flat_illustration"

    themes = [i.strip() for i in (subject.get("icon_themes") or "").split(",") if i.strip()]
    label_list = [i.strip() for i in (subject.get("short_labels") or "").split(";") if i.strip()]
    if label_list:
        brief["infographic_suggestions"] = label_list[:4]
    icons = [str(x) for x in pattern_icons[:4]] + themes
    # Deduplicate preserving order
    seen_i: set[str] = set()
    icons_u: list[str] = []
    for i in icons:
        k = i.lower()
        if k not in seen_i:
            seen_i.add(k)
            icons_u.append(i)
    if icons_u:
        brief["icon_suggestions"] = icons_u[:4]
        brief["icons"] = icons_u[:4]

    if brand_palette:
        brief["color_palette"] = list(brand_palette)

    meta = dict(brief.get("metadata") or {})
    meta.update(subject)
    meta["content_grounded"] = True
    meta["text_in_image"] = True  # short labels only
    meta["visual_plan"] = {
        "post_intent": plan.get("post_intent"),
        "pattern_id": plan.get("pattern_id"),
        "message": plan.get("message"),
        "story": plan.get("story"),
        "quality": plan.get("quality"),
        "design_tokens": plan.get("design_tokens"),
        "linkedin_image_type": plan.get("linkedin_image_type"),
        "layout_strategy": plan.get("layout_strategy"),
        "style_inspiration": plan.get("style_inspiration"),
        "thought_leadership_mode": plan.get("thought_leadership_mode"),
    }
    meta["visual_pattern_id"] = plan.get("pattern_id")
    meta["post_intent"] = plan.get("post_intent")
    meta["visual_story"] = (plan.get("story") or {}).get("narrative")
    meta["visual_hierarchy"] = (plan.get("story") or {}).get("visual_hierarchy")
    meta["planning_clause"] = planning_clause
    meta["style_inspiration"] = plan.get("style_inspiration")
    meta["design_token_summary"] = plan.get("design_tokens")
    meta["visual_quality_score"] = (plan.get("quality") or {}).get("overall")
    brief["metadata"] = meta

    avoid_extra = ", ".join(str(a) for a in (plan.get("always_avoid") or [])[:16])
    brief["negative_prompt"] = (
        "No text paragraphs, no watermark, no signatures, no blurry image, "
        "no extra fingers, no distorted objects, no AI artifacts, no random symbols, "
        "no spelling errors, no floating UI chrome, no fake logos, no unrealistic humans, "
        "no meme style, no cartoon clipart, no robots, no glowing brains, "
        "LinkedIn logo, social media UI chrome, paragraphs of body copy, "
        "tiny illegible text walls, misspelled words, garbled typography, "
        "long question headline across the top, truncated cut-off text at edges, "
        "title-card only layout, watermark, low quality, muddy brown background, "
        "muddy beige olive gradient, dull washed-out colours, neon cyberpunk glow, "
        "black void background, rim-light portrait collage, "
        "floating icon halo around angry businessman, photorealistic stock photo, "
        "padlock spam, hacking hoodie, cluttered mind-map spiderweb, "
        "duplicate repeated labels, misspelled Distributor Distrubur Diligence, "
        "synonym spam Vendor Provider Reseller Distributor Supplier all at once, "
        f"{avoid_extra}"
    )
    return brief
