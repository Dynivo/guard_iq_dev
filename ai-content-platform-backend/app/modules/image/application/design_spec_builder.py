"""Build and validate VisualDesignSpec from draft content (heuristic + optional LLM)."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.core.logging import get_logger
from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.design_spec import (
    ARCHETYPE_IDS,
    DesignBrandColors,
    DesignLayoutSpec,
    DesignLogoSpec,
    VisualDesignSpec,
)

logger = get_logger(__name__)

_STAT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?%|\d+(?:\.\d+)?\s*[xX]|\d+(?:\.\d+)?\s*(?:tbps|Tbps|TBPS|"
    r"million|billion|k\b)|\$\d[\d,]*(?:\.\d+)?|\d{1,4}\+?)\b",
    re.I,
)
_YEAR_RE = re.compile(r"^20\d{2}$")


@lru_cache(maxsize=1)
def _archetypes_cfg() -> dict[str, Any]:
    return load_yaml("archetypes.yaml")


@lru_cache(maxsize=1)
def _vocab_cfg() -> dict[str, Any]:
    return load_yaml("visual_vocabulary.yaml")


@lru_cache(maxsize=1)
def _quality_cfg() -> dict[str, Any]:
    return load_yaml("quality_rules.yaml")


def _clean_words(text: str, max_words: int, max_chars: int) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = re.sub(r"#\w+", "", t).strip()
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words])
    if len(t) > max_chars:
        # Never use ellipsis in image copy — cut on a word boundary only
        t = t[:max_chars].rsplit(" ", 1)[0].rstrip(" ,.-;:")
    return t.strip(" ,.-")


def _extract_stats(text: str, limit: int = 4) -> list[str]:
    """Extract significant stats only — ignore bare small integers (noise)."""
    q = (_quality_cfg().get("stats") or {}) if _quality_cfg() else {}
    min_mag = int(q.get("min_significant_magnitude") or 50)
    found: list[str] = []
    for m in _STAT_RE.finditer(text or ""):
        raw = m.group(1).strip()
        if _YEAR_RE.match(raw):
            continue
        end = m.end()
        if end < len(text or "") and (text or "")[end] == "+" and not raw.endswith("+"):
            raw = raw + "+"
        if raw not in found:
            found.append(raw)
        if len(found) >= limit * 3:
            break

    def is_significant(s: str) -> bool:
        sl = s.lower().replace(" ", "")
        if any(u in sl for u in ("%", "x", "+", "tbps", "million", "billion", "$", "k")):
            return True
        digits = re.sub(r"[^\d]", "", s)
        if not digits.isdigit():
            return False
        return int(digits) >= min_mag

    def score(s: str) -> tuple[int, int]:
        sl = s.lower()
        priority = 0
        if "+" in s:
            priority += 50
        if re.search(r"\d+\s*x\b", sl) or sl.endswith("x"):
            priority += 40
        if any(u in sl for u in ("%", "tbps", "million", "billion", "$")):
            priority += 30
        digits = re.sub(r"[^\d]", "", s)
        magnitude = int(digits) if digits.isdigit() else 0
        if magnitude >= 100:
            priority += 20
        # Prefer mid-size finding counts over tiny noise
        if 10 <= magnitude < 50:
            priority += 15
        return (priority, magnitude)

    significant = [s for s in found if is_significant(s)]
    # Promote numbers that appear inside fact phrases (e.g. "19 unsanctioned actions")
    for phrase in _extract_fact_phrases(text or "", limit=6):
        m = re.match(r"(\d+\+?)", phrase)
        if not m:
            continue
        raw = m.group(1)
        if raw not in significant:
            significant.append(raw)
    significant.sort(key=score, reverse=True)
    return significant[:limit]


def _punchy_cta(cta: str, archetype_id: str) -> str:
    """Prefer complete short CTAs — never leave a dangling clause."""
    defaults = {
        "statistic_threat_alert": "ARE YOU PREPARED?",
        "news_alert": "REVIEW YOUR SECURITY POSTURE",
        "threat_risk_map": "CHECK YOUR EXPOSURE",
        "explainer_infographic": "SAVE THIS FOR LATER",
        "minimal_editorial": "WHAT WOULD YOU DO?",
        "quote_insight": "SHARE YOUR TAKE",
        "data_infographic": "REVIEW THE NUMBERS",
        "comparison": "WHICH SIDE ARE YOU ON?",
    }
    t = re.sub(r"\s+", " ", (cta or "").strip())
    t = re.sub(r"#\w+", "", t).strip(" ?!.")
    dangling = t.upper().endswith((" YOUR", " THE", " A", " AN", " TO", " FOR", " OF"))
    words = t.split()
    # Long questions belong in the headline, not the CTA plate
    is_long_question = ("?" in (cta or "")) or len(words) > 6 or t.lower().startswith(
        ("when ", "how ", "what ", "why ", "could ", "would ", "have you", "are you")
    )
    if not t or dangling or len(words) > 8 or len(t) > 48 or is_long_question:
        return defaults.get(archetype_id, "REVIEW YOUR SECURITY POSTURE")
    return t.upper()


_FACT_NOUN = (
    r"(?:unsanctioned\s+)?(?:actions?|attacks?|breaches?|incidents?|agents?|"
    r"test\s+runs?|runs?|identities|vulnerabilit(?:y|ies)|findings?)"
)
_FACT_PHRASE_RE = re.compile(
    rf"\b(\d{{1,4}}\+?\s+{_FACT_NOUN})\b",
    re.I,
)
_VAGUE_OPENERS = (
    "revealed something",
    "something unsettling",
    "wake-up call",
    "in case you missed",
    "the report underscores",
    "the report highlights",
)


def _extract_fact_phrases(text: str, limit: int = 4) -> list[str]:
    """Pull concrete fact labels like '19 unsanctioned actions' from body copy."""
    found: list[str] = []
    for m in _FACT_PHRASE_RE.finditer(text or ""):
        phrase = re.sub(r"\s+", " ", m.group(1).strip())
        phrase = phrase[0].upper() + phrase[1:] if phrase else phrase
        if phrase.lower() not in {x.lower() for x in found}:
            found.append(phrase)

    def rank(p: str) -> tuple[int, int]:
        pl = p.lower()
        score = 0
        if "unsanctioned" in pl:
            score += 60
        if any(k in pl for k in ("action", "attack", "breach", "incident", "identit")):
            score += 40
        if "test run" in pl or re.search(r"\bruns?\b", pl):
            score += 5
        digits = re.sub(r"[^\d]", "", p)
        mag = int(digits) if digits.isdigit() else 0
        return (score, mag)

    found.sort(key=rank, reverse=True)
    return found[:limit]


def _score_fact_sentence(s: str) -> int:
    """Higher = better supporting line for an image (concrete facts over vague openers)."""
    lower = s.lower()
    score = 0
    if re.search(r"\d", s):
        score += 40
    if _FACT_PHRASE_RE.search(s):
        score += 35
    for k in (
        "anthropic",
        "openai",
        "fake",
        "unsanctioned",
        "unauthor",
        "unauthorized",
        "agent",
        "mitigated",
        "surged",
        "breach",
        "attack",
        "tbps",
        "institute",
    ):
        if k in lower:
            score += 12
    for v in _VAGUE_OPENERS:
        if v in lower:
            score -= 50
    words = len(s.split())
    if words < 6:
        score -= 20
    if words > 22:
        score -= 15
    if s.startswith("#"):
        score -= 100
    return score


def _best_subheadline(body: str, hook: str = "") -> str:
    """Pick the most fact-dense sentence — never settle for a vague teaser opener."""
    sentences = re.split(r"(?<=[.!?])\s+", (body or "").strip())
    ranked: list[tuple[int, str]] = []
    for sent in sentences:
        s = sent.strip()
        if not s or s.startswith("#"):
            continue
        if hook and len(hook) >= 12 and s.lower().startswith(hook[:20].lower()):
            continue
        if len(s.split()) < 5:
            continue
        ranked.append((_score_fact_sentence(s), s))
    if not ranked:
        phrases = _extract_fact_phrases(body, limit=2)
        if phrases:
            return _clean_words(
                f"{phrases[0]} found in UK AI security evaluations.", 18, 110
            )
        return ""
    ranked.sort(key=lambda x: x[0], reverse=True)
    best_score, best = ranked[0]
    if best_score < 10:
        for _score, s in ranked:
            if re.search(r"\d", s):
                best = s
                break
        else:
            best = ranked[0][1]
    # Compact long multi-clause lines: keep clauses that carry numbers/facts
    if len(best) > 110 or len(best.split()) > 18:
        phrases = _extract_fact_phrases(best or body, limit=1)
        clauses = re.split(r",\s+", best)
        digit_clauses = [c for c in clauses if re.search(r"\d", c)]
        if phrases and digit_clauses:
            joined = ", ".join(digit_clauses[:2]).rstrip(",;")
            if "identified" in best.lower() and "identified" not in joined.lower():
                joined = f"{joined} identified"
            if not joined.endswith((".", "!", "?")):
                joined += "."
            return _clean_words(joined, 18, 110)
        if phrases:
            return _clean_words(f"{phrases[0]} identified.", 12, 72)
    return _clean_words(best, 18, 110)


def _shorten_impact(s: str, *, max_words: int = 16, max_chars: int = 100) -> str:
    t = re.sub(r"\s+", " ", (s or "").strip())
    # Prefer clause before em-dash / semicolon for CTA cards
    for sep in (" — ", " – ", "; ", " and your entire"):
        if sep in t.lower() or sep in t:
            # case-sensitive split attempt
            idx = t.lower().find(sep.lower()) if sep.startswith(" and") else t.find(sep)
            if idx > 20:
                t = t[:idx].strip(" ,;")
                break
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words]).rstrip(",;")
    if len(t) > max_chars:
        t = t[: max_chars - 1].rsplit(" ", 1)[0].rstrip(",;")
    if t and not t.endswith((".", "!", "?")):
        t += "."
    return t


def _complete_cta_body(text: str) -> str:
    """Keep CTA body as a complete impact sentence (no mid-clause ellipsis)."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return "Assess AI tools before they touch client data or regulated workflows."
    if len(t) <= 100 and len(t.split()) <= 18:
        if not t.endswith((".", "!", "?")):
            t += "."
        return t
    shortened = _shorten_impact(t, max_words=16, max_chars=100)
    if shortened and len(shortened.split()) >= 6:
        return shortened
    return "Assess AI tools before they touch client data or regulated workflows."


def _pick_cta_body(*, body: str, hook: str, sub: str, topic_id: str) -> str:
    """Story-specific impact line for the CTA card — not a generic downtime filler."""
    sentences = re.split(r"(?<=[.!?])\s+", (body or "").strip())
    ranked: list[tuple[int, str]] = []
    for sent in sentences:
        s = sent.strip()
        if not s or s.startswith("#"):
            continue
        if hook and len(hook) >= 12 and s.lower().startswith(hook[:20].lower()):
            continue
        if sub and s.lower().startswith(sub[:24].lower()):
            continue
        words = len(s.split())
        if words < 6:
            continue
        lower = s.lower()
        score = 0
        # Prefer "so what" / implication lines
        for k in (
            "imagine the risk",
            "client data",
            "compliance",
            "wake-up",
            "need to",
            "means you",
            "regulated",
            "assess",
            "bypass",
            "safeguard",
            "trust",
            "breach",
            "downtime",
            "prepared",
        ):
            if k in lower:
                score += 15
        if lower.startswith(("if ", "that means", "for regulated", "it means")):
            score += 20
        # Deprioritize pure news restatement
        if any(k in lower for k in ("reuters", "blog post", "disclosed on")):
            score -= 40
        if _score_fact_sentence(s) > 60 and score < 20:
            score -= 10  # facts belong in sub/stat, not CTA
        if words > 28:
            score -= 10
        if score > 0:
            ranked.append((score, s))
    if ranked:
        ranked.sort(key=lambda x: x[0], reverse=True)
        return _complete_cta_body(ranked[0][1])

    topic_defaults = {
        "ddos": "Even brief downtime can trigger compliance breaches and lost client trust.",
        "identity": "Fake identities and weak AI safeguards put client data and compliance at risk.",
        "ai_agents": "If AI can bypass security in a test, imagine the risk to client data.",
        "breach": "One bypass in testing can become a client-data incident in production.",
    }
    return topic_defaults.get(
        topic_id,
        "Assess AI tools before they touch client data or regulated workflows.",
    )


def _clean_tagline(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    # Prefer a complete short services line over a clipped long one
    if "|" in t:
        # "Guard IQ | Managed IT & Security for Regulated…" → use right side if short enough
        right = t.split("|", 1)[1].strip()
        if 12 <= len(right) <= 42 and not right.lower().endswith((" for", " and", " the")):
            t = right
        elif "managed" in t.lower():
            t = "IT & Security Managed For You"
    if len(t) <= 42 and not t.lower().endswith((" for", " and", " the", " of")):
        return t
    if len(t) > 42:
        t = t[:41].rsplit(" ", 1)[0].rstrip(",.;:")
    if t.lower().endswith((" for", " and", " the", " of", " a")):
        t = "IT & Security Managed For You"
    return t


def _tokens_overlap(a: str, b: str) -> bool:
    """True when a's meaningful tokens are largely already inside b (duplicate copy)."""
    stop = {"the", "a", "an", "of", "in", "for", "to", "and", "were", "was", "with"}
    ta = {w for w in re.findall(r"[a-z0-9+]+", (a or "").lower()) if w not in stop and len(w) > 1}
    tb = {w for w in re.findall(r"[a-z0-9+]+", (b or "").lower()) if w not in stop and len(w) > 1}
    if not ta:
        return False
    return len(ta & tb) / len(ta) >= 0.7


def _distinct_secondary_insight(body: str, *, used: str) -> str:
    """Pull a SECOND distinct insight (org / attribution) not already on the card."""
    used_l = (used or "").lower()
    patterns = [
        (
            r"(Anthropic(?:'s)?\s+agent\s+responsible\s+for\s+\d+)",
            lambda m: m.group(1)[0].upper() + m.group(1)[1:],
        ),
        (
            r"(Anthropic(?:'s)?\s+agent\s+was\s+behind\s+\d+)",
            lambda m: "Anthropic agent behind " + re.search(r"\d+", m.group(1)).group(0),
        ),
        (
            r"((?:Britain'?s\s+)?AI Security Institute)",
            lambda m: "Source: UK AI Security Institute",
        ),
        (
            r"(OpenAI(?:'s)?\s+agent\s+the\s+remaining\s+\d+)",
            lambda m: m.group(1)[0].upper() + m.group(1)[1:],
        ),
        (
            r"(fake online identities)",
            lambda m: "Agent created fake online identities",
        ),
    ]
    for pat, fmt in patterns:
        m = re.search(pat, body or "", re.I)
        if not m:
            continue
        phrase = fmt(m)
        if _tokens_overlap(phrase, used_l):
            continue
        return _clean_words(phrase, 10, 48)
    return ""


def _dedupe_visual_fields(
    *,
    subheadline: str,
    primary_stat: str,
    supporting: tuple[str, ...],
    body: str,
) -> tuple[str, str, tuple[str, ...]]:
    """Ensure the same finding is not shown as both subheadline and giant stat."""
    sub = (subheadline or "").strip()
    primary = (primary_stat or "").strip()
    supp = list(supporting)

    # Drop supporting items that duplicate sub or primary
    supp = [s for s in supp if s and not _tokens_overlap(s, sub) and not _tokens_overlap(s, primary)]

    if primary and sub and _tokens_overlap(primary, sub):
        # Key fact already in subheadline — omit giant repeat; add distinct insight instead
        primary = ""
        distinct = _distinct_secondary_insight(body, used=f"{sub} {primary_stat}")
        if distinct and not _tokens_overlap(distinct, sub):
            supp = [distinct] + [s for s in supp if not _tokens_overlap(s, distinct)]
        supp = supp[:2]
    elif primary and any(_tokens_overlap(primary, s) for s in supp):
        supp = [s for s in supp if not _tokens_overlap(primary, s)]
        distinct = _distinct_secondary_insight(body, used=f"{sub} {primary}")
        if distinct:
            supp = [distinct] + supp
        supp = supp[:2]

    return sub, primary, tuple(supp[:2])


def _short_subheadline(body: str, hook: str = "") -> str:
    return _best_subheadline(body, hook=hook)

def _extract_bullets(body: str, limit: int = 5) -> list[str]:
    bullets = re.findall(r"(?:^|\n)\s*(?:[-•*]|\d+[.)])\s+(.+)", body or "")
    out: list[str] = []
    for b in bullets:
        s = _clean_words(b, 8, 48)
        if s and s.lower() not in {x.lower() for x in out}:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def resolve_motifs(text: str) -> tuple[str, tuple[str, ...]]:
    """Return (topic_id, motifs) from visual vocabulary."""
    cfg = _vocab_cfg()
    topics = cfg.get("topics") or {}
    lower = (text or "").lower()
    best_id = ""
    best_motifs: list[str] = list(cfg.get("default_motifs") or ["shield", "network"])
    best_hits = 0
    for tid, spec in topics.items():
        if not isinstance(spec, dict):
            continue
        keys = [str(k).lower() for k in (spec.get("keywords") or ())]
        hits = sum(1 for k in keys if k and k in lower)
        if hits > best_hits:
            best_hits = hits
            best_id = str(tid)
            best_motifs = [str(m) for m in (spec.get("motifs") or best_motifs)]
    return best_id, tuple(best_motifs[:6])


def classify_archetype(
    *,
    hook: str,
    body: str,
    cta: str = "",
    content_type: str = "",
    stats: list[str] | None = None,
    visual_style: str | None = None,
) -> str:
    """Select design archetype from content signals + optional UI style override."""
    cfg = _archetypes_cfg()
    aliases = cfg.get("style_aliases") or {}
    style = (visual_style or "auto").strip().lower()
    forced = aliases.get(style)
    if forced and str(forced) in ARCHETYPE_IDS:
        return str(forced)

    text = f"{hook}\n{body}\n{cta}"
    lower = text.lower()
    stats = stats if stats is not None else _extract_stats(text)
    bullets = _extract_bullets(body)

    if any(k in lower for k in ("breaking", "alert", "just announced", "this week", "surge")):
        if stats:
            return "statistic_threat_alert"
        return "news_alert"
    if any(
        k in lower
        for k in (
            "unsanctioned",
            "fake online identities",
            "fake identities",
            "ai agent",
            "ai agents",
            "security institute",
            "unauthorised actions",
            "unauthorized actions",
        )
    ):
        if stats or _extract_fact_phrases(text):
            return "statistic_threat_alert"
        return "news_alert"
    if any(k in lower for k in (" vs ", "versus", "compared to", "before", "after", "rather than")):
        return "comparison"
    if len(bullets) >= 3 or any(
        k in lower for k in ("step 1", "how to", "3 things", "five ways", "checklist")
    ):
        return "explainer_infographic"
    if any(k in lower for k in ("risk", "vector", "attack path", "exposure")) and len(bullets) >= 2:
        return "threat_risk_map"
    if stats and (
        any(k in lower for k in ("%", "x this", "surged", "increased", "mitigated", "attacks"))
        or len(stats) >= 1
    ):
        if len(stats) >= 2:
            return "data_infographic"
        return "statistic_threat_alert"
    if content_type in {"personal_achievement", "thought_leadership"} or any(
        k in lower for k in ("i believe", "in my experience", "the truth is")
    ):
        return "quote_insight"
    if len(hook.split()) <= 14 and not stats:
        return "minimal_editorial"
    return "minimal_editorial"


def archetype_meta(archetype_id: str) -> dict[str, Any]:
    cfg = _archetypes_cfg()
    arch = (cfg.get("archetypes") or {}).get(archetype_id) or {}
    return dict(arch) if isinstance(arch, dict) else {}


def variant_archetype(primary: str, variant_index: int) -> str:
    """Pick a distinct archetype for variant_index > 0."""
    if variant_index <= 0:
        return primary
    rotation = list((_archetypes_cfg().get("variant_rotation") or list(ARCHETYPE_IDS)))
    ordered = [primary] + [a for a in rotation if a != primary]
    return ordered[variant_index % len(ordered)]


def apply_quality_rules(spec: VisualDesignSpec) -> VisualDesignSpec:
    """Truncate / thin content to keep layouts readable."""
    q = _quality_cfg()
    h = q.get("headline") or {}
    s = q.get("subheadline") or {}
    p = q.get("primary_stat") or {}
    ss = q.get("supporting_stat") or {}
    c = q.get("cta") or {}
    blocks = q.get("content_blocks") or {}

    headline = _clean_words(
        spec.headline, int(h.get("max_words") or 12), int(h.get("max_chars") or 72)
    )
    subheadline = _clean_words(
        spec.subheadline, int(s.get("max_words") or 20), int(s.get("max_chars") or 120)
    )
    primary_stat = _clean_words(spec.primary_stat, 6, int(p.get("max_chars") or 32))
    max_stats = int(ss.get("max_items") or 4)
    supporting = tuple(
        _clean_words(x, 6, int(ss.get("max_chars") or 36))
        for x in spec.supporting_stats[:max_stats]
        if str(x).strip()
    )
    cta = _punchy_cta(spec.cta, spec.design_archetype)
    cta = _clean_words(cta, int(c.get("max_words") or 10), int(c.get("max_chars") or 64))
    # Never leave dangling CTA after hard truncate
    if cta.upper().endswith((" YOUR", " THE", " A", " AN", " TO", " FOR", " OF")):
        cta = _punchy_cta("", spec.design_archetype)
    max_blocks = int(blocks.get("max_items") or 5)
    if spec.layout.density == "low":
        max_blocks = min(max_blocks, int((q.get("density") or {}).get("max_low_blocks") or 2))
    content_blocks = tuple(spec.content_blocks[:max_blocks])
    source = _clean_words(spec.source, 6, int((q.get("source") or {}).get("max_chars") or 40))

    return VisualDesignSpec(
        format=spec.format,
        design_archetype=spec.design_archetype,
        headline=headline,
        subheadline=subheadline,
        primary_stat=primary_stat,
        supporting_stats=supporting,
        visual_concept=spec.visual_concept,
        visual_elements=spec.visual_elements,
        content_blocks=content_blocks,
        cta=cta,
        cta_body=_complete_cta_body(spec.cta_body),
        source=source,
        category_label=_clean_words(spec.category_label, 4, 32),
        brand_name=spec.brand_name,
        tagline=_clean_tagline(spec.tagline),
        logo=spec.logo,
        brand=spec.brand,
        layout=spec.layout,
        typography_template=spec.typography_template,
        brand_variant=spec.brand_variant,
        visual_motifs=spec.visual_motifs,
        metadata={**spec.metadata, "quality_rules_applied": True},
    )


def build_design_spec(
    *,
    hook: str = "",
    body: str = "",
    cta: str = "",
    title: str = "",
    content_type: str = "",
    brand: dict[str, Any] | None = None,
    source: str = "",
    visual_style: str | None = None,
    include_logo: bool | None = None,
    logo_position: str | None = None,
    logo_size: str | None = None,
    variant_index: int = 0,
    forced_archetype: str | None = None,
) -> VisualDesignSpec:
    """Heuristic design-spec builder (no LLM required; LLM can refine later)."""
    brand = brand or {}
    text = f"{hook}\n{body}"
    stats = _extract_stats(text)
    bullets = _extract_bullets(body)
    topic_id, motifs = resolve_motifs(text)

    primary = forced_archetype or classify_archetype(
        hook=hook,
        body=body,
        cta=cta,
        content_type=content_type,
        stats=stats,
        visual_style=visual_style,
    )
    if primary not in ARCHETYPE_IDS:
        # Allow newly configured YAML archetypes not yet mirrored in ARCHETYPE_IDS
        yaml_ids = set((_archetypes_cfg().get("archetypes") or {}).keys())
        if primary not in yaml_ids:
            primary = "minimal_editorial"
    archetype_id = variant_archetype(primary, variant_index)
    meta = archetype_meta(archetype_id)

    headline_src = (hook or title or "").strip()
    headline = headline_src or "Security insight"

    # Without significant stats, prefer editorial — never invent random numbers
    if not stats and archetype_id in {
        "statistic_threat_alert",
        "data_infographic",
    }:
        archetype_id = "minimal_editorial" if variant_index == 0 else archetype_id
        meta = archetype_meta(archetype_id)

    primary_stat = stats[0] if stats else ""
    supporting = tuple(stats[1:3]) if len(stats) > 1 else ()
    fact_phrases = _extract_fact_phrases(text, limit=4)
    # Prefer a statistic that appears in the headline when present (story-first)
    hook_stats = _extract_stats(hook or title or "", limit=3)
    if hook_stats:
        primary_stat = hook_stats[0]
        rest = [s for s in stats if s != primary_stat]
        supporting = tuple(rest[:2])
    elif fact_phrases:
        # Use full fact label as primary ("19 unsanctioned actions") — not a naked 19
        primary_stat = _clean_words(fact_phrases[0], 5, 28)
        # Supporting: next fact or leftover numeric stats
        extra: list[str] = []
        for fp in fact_phrases[1:3]:
            extra.append(_clean_words(fp, 5, 28))
        for s in stats:
            if s not in primary_stat and all(s not in e for e in extra):
                extra.append(s)
            if len(extra) >= 2:
                break
        supporting = tuple(extra[:2])
    if primary_stat and "+" not in primary_stat and re.fullmatch(r"\d+", primary_stat or ""):
        m = re.search(rf"{re.escape(primary_stat)}\+", text)
        if m:
            primary_stat = m.group(0)

    sub = _best_subheadline(body, hook=hook)
    sub, primary_stat, supporting = _dedupe_visual_fields(
        subheadline=sub,
        primary_stat=primary_stat,
        supporting=supporting,
        body=body,
    )

    # Cards only for explainer / risk map with real bullets — never naked numbers
    content_blocks = tuple(bullets[:3])
    if archetype_id == "threat_risk_map" and not content_blocks:
        content_blocks = tuple(x.replace("_", " ").title() for x in motifs[:3])
    # Keep stats on news/editorial when we extracted real findings
    if archetype_id in {"minimal_editorial", "quote_insight"} and not primary_stat:
        content_blocks = ()
        supporting = ()
    elif archetype_id in {"news_alert", "minimal_editorial", "quote_insight"}:
        content_blocks = ()

    # Upgrade soft editorial → threat alert when we have concrete findings
    if (primary_stat or supporting) and archetype_id == "minimal_editorial":
        archetype_id = "statistic_threat_alert"
        meta = archetype_meta(archetype_id)

    # Brand surface + logo placement — auto from content unless UI overrides
    style_l = (visual_style or "auto").strip().lower()
    brand_variant = str(meta.get("brand_variant") or "dark")
    if style_l in {"infographic", "data_story", "explainer", "light", "light_infographic"}:
        brand_variant = "light"
        if style_l in {"infographic", "data_story"} and archetype_id in {
            "statistic_threat_alert",
            "news_alert",
        }:
            archetype_id = "data_infographic"
            meta = archetype_meta(archetype_id)
            brand_variant = "light"
    elif style_l in {"threat_alert", "editorial", "minimal", "dark"}:
        brand_variant = "dark"
    elif style_l in {"auto", ""}:
        # Automatic theme from post shape
        lower_all = f"{hook}\n{body}\n{cta}".lower()
        wants_light = archetype_id in {
            "data_infographic",
            "explainer_infographic",
            "comparison",
            "threat_risk_map",
        } or (
            bool(primary_stat)
            and any(k in lower_all for k in ("how to", "checklist", "steps", "vs ", "framework"))
        )
        wants_dark = archetype_id in {
            "statistic_threat_alert",
            "news_alert",
            "minimal_editorial",
            "quote_insight",
        } or any(
            k in lower_all
            for k in (
                "alert",
                "unsanctioned",
                "fake identities",
                "breach",
                "ransomware",
                "could your",
                "are you prepared",
            )
        )
        if wants_light and not wants_dark:
            brand_variant = "light"
            if archetype_id == "statistic_threat_alert":
                archetype_id = "data_infographic"
                meta = archetype_meta(archetype_id)
        else:
            brand_variant = "dark"
        # Multi-variant: alternate surface for variety
        if variant_index % 2 == 1:
            brand_variant = "light" if brand_variant == "dark" else "dark"
            if brand_variant == "light" and archetype_id in {
                "statistic_threat_alert",
                "news_alert",
            }:
                archetype_id = "data_infographic"
                meta = archetype_meta(archetype_id)
    elif variant_index % 2 == 1:
        brand_variant = "light"
        if archetype_id in {"statistic_threat_alert", "news_alert"}:
            archetype_id = "data_infographic"
            meta = archetype_meta(archetype_id)

    # Background / accent from brand kit with theme-aware defaults
    if brand_variant == "light":
        primary_color = str(brand.get("primary_color") or "#0A1F2B")
        accent = str(brand.get("accent_color") or "#0D5C63")
        secondary = str(brand.get("secondary_color") or "#F4F6F8")
        bg_color = str(brand.get("background_color") or "#F4F6F8")
    else:
        primary_color = str(brand.get("primary_color") or "#0A1F2B")
        accent = str(brand.get("accent_color") or "#4FC3F7")
        secondary = str(brand.get("secondary_color") or "#FFFFFF")
        bg_color = primary_color

    category = ""
    if archetype_id in {"statistic_threat_alert", "news_alert", "data_infographic"}:
        if topic_id in {"ddos", "ransomware", "malware", "breach"}:
            category = "CYBER THREAT ALERT"
        elif topic_id in {"ai_agents", "identity"}:
            category = "AI SECURITY ALERT"
        else:
            category = "SECURITY INSIGHT"

    visual_concept = (
        f"{'Light consulting infographic' if brand_variant == 'light' else 'Dark navy editorial'} "
        f"for {topic_id or 'enterprise security'}: "
        f"({', '.join(motifs[:2]) or 'shield'}), "
        f"clear hierarchy, no duplicate stats, leave logo space only."
    )

    canvas = (_archetypes_cfg().get("canvas") or {}) if _archetypes_cfg() else {}

    # Logo always on by default (UI can still turn off explicitly)
    logo_enabled = True if include_logo is None else bool(include_logo)

    # Auto logo position from theme (override only if caller passed a concrete position)
    default_pos = "top_center" if brand_variant == "dark" else "bottom_right"
    pos = (logo_position or "").strip()
    if pos in {"brand_default", "auto", ""}:
        pos = default_pos

    cta_text = _punchy_cta(cta, archetype_id)

    cta_body = _pick_cta_body(body=body, hook=hook, sub=sub, topic_id=topic_id)

    brand_name = str(brand.get("name") or brand.get("brand_name") or "Guard IQ").strip() or "Guard IQ"
    tagline = _clean_tagline(
        str(
            brand.get("services_line")
            or brand.get("footer_text")
            or brand.get("tagline")
            or "IT & Security Managed For You"
        )
    )
    if not category:
        category = "SECURITY INSIGHT"
    spec = VisualDesignSpec(
        format="linkedin_square",
        design_archetype=archetype_id,
        headline=headline,
        subheadline=sub,
        primary_stat=primary_stat,
        supporting_stats=supporting,
        visual_concept=visual_concept,
        visual_elements=motifs,
        content_blocks=content_blocks,
        cta=cta_text,
        cta_body=cta_body,
        source=(source or "").strip(),
        category_label=category,
        brand_name=brand_name,
        tagline=tagline,
        logo=DesignLogoSpec(
            enabled=logo_enabled,
            position=pos,
            size=str(logo_size or "m").lower(),
        ),
        brand=DesignBrandColors(
            primary=primary_color,
            secondary=secondary,
            background=bg_color,
            text="#FFFFFF" if brand_variant == "dark" else primary_color,
            accent=accent,
        ),
        layout=DesignLayoutSpec(
            type=str(meta.get("layout_type") or "editorial"),
            columns=2 if archetype_id in {"comparison", "data_infographic"} else 1,
            density=str(meta.get("density") or "medium"),
            width=int(canvas.get("width") or 1080),
            height=int(canvas.get("height") or 1080),
        ),
        typography_template=str(meta.get("typography_template") or "hero"),
        brand_variant=brand_variant,
        visual_motifs=motifs,
        metadata={
            "topic_id": topic_id,
            "primary_archetype": primary,
            "variant_index": variant_index,
            "visual_style": visual_style or "auto",
            "brand_variant": brand_variant,
            "logo_position": pos,
            "renderer": "chatgpt_images_only",
        },
    )
    validated = apply_quality_rules(spec)
    logger.info(
        "image_design_spec_created archetype=%s topic=%s variant=%s",
        validated.design_archetype,
        topic_id,
        variant_index,
    )
    logger.info(
        "image_archetype_selected archetype=%s primary=%s style=%s",
        validated.design_archetype,
        primary,
        visual_style or "auto",
    )
    return validated


def illustration_prompt_clause(spec: VisualDesignSpec) -> str:
    """Text-free visual direction for the image provider."""
    motifs = ", ".join(spec.visual_motifs[:3]) or "shield, network"
    return (
        f"{spec.visual_concept} Motifs: {motifs}. "
        "Quiet dark navy editorial BACKGROUND only, single soft cybersecurity metaphor, "
        "large empty fields, no diagrams, no connected circles, no icon grids, "
        "no text, no letters, no numbers, no logos, no watermarks, no labels."
    )

