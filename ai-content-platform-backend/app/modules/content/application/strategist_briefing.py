"""Strategist Copilot briefing — deterministic narrative templates (Phase 1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _greeting(now: datetime | None = None) -> str:
    hour = (now or datetime.now()).hour
    if hour < 12:
        return "Good morning."
    if hour < 17:
        return "Good afternoon."
    return "Good evening."


def build_strategist_briefing(
    *,
    opportunities: list[dict[str, Any]],
    summary: dict[str, Any],
    trends: list[dict[str, Any]],
    brand: dict[str, Any],
    memory: list[str],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Compose Copilot payload from composed opportunities + briefing counts."""
    high = [o for o in opportunities if o.get("priority") == "high"]
    today = [o for o in opportunities if o.get("timeline_bucket") == "today"]
    top = (today or high or opportunities)[:1]
    later = [o for o in opportunities if o not in top][:6]

    top_opp = top[0] if top else None
    narrative: list[str] = []

    analysed = int(summary.get("articles_analysed") or 0)
    opp_n = int(summary.get("opportunities") or 0)
    trend_n = int(summary.get("trends") or 0)

    plan = summary.get("plan_health") or {}
    window_mode = (plan.get("window") or {}).get("mode") or "fortnight"
    window_label = "week" if window_mode == "weekly" else "fortnight"

    if analysed or opp_n:
        narrative.append(
            f"We analysed {analysed} articles this {window_label} and surfaced {opp_n} content opportunities"
            + (f" across {trend_n} trends." if trend_n else ".")
        )
    else:
        narrative.append(
            "No screened opportunities yet — score news as relevant or capture a success story to begin."
        )

    if top_opp:
        audiences = ", ".join(top_opp.get("audiences") or []) or "your audience"
        narrative.append(
            f"Based on {audiences}, I recommend posting about “{top_opp['title']}” today."
        )
        if top_opp.get("timing_advice"):
            narrative.append(str(top_opp["timing_advice"]) + ".")
        # Avoid theme: pick a declining / low-priority topic from trends if any
        if trends and len(opportunities) > 1:
            low = [o for o in opportunities if o.get("priority") == "low"]
            if low:
                narrative.append(
                    f"Deprioritise “{low[0]['title']}” for now — estimated fit is weaker this week."
                )
    elif trends:
        key = trends[0].get("topic_key") or "a rising topic"
        narrative.append(f"Watching trend “{key}” — rescore related news to unlock opportunities.")

    goal_statement = (
        brand.get("strategic_goal")
        or config.get("default_strategic_goal")
        or "Become a trusted authority through consistent, high-signal LinkedIn content."
    )
    counts = plan.get("counts") or {}
    target = plan.get("target") or {}
    gaps = plan.get("gaps") or {}
    total_gap = sum(int(gaps.get(k) or 0) for k in ("educational", "success_story", "personal_achievement"))
    total_c = sum(int(counts.get(k) or 0) for k in ("educational", "success_story", "personal_achievement"))
    total_t = int(target.get("total") or 10) or 10
    # Progress blends mix completion with average opportunity quality
    mix_pct = min(100, int(round(100 * total_c / total_t)))
    avg = int(summary.get("average_opportunity_score") or 0)
    progress = clamp_mix(mix_pct, avg)

    recommended_action = None
    if total_gap > 0:
        recommended_action = {
            "label": "Regenerate plan",
            "action": "regenerate_plan",
            "opportunity_id": top_opp["id"] if top_opp else "",
            "content_type": "educational",
            "primary_article_id": top_opp.get("primary_article_id") if top_opp else None,
            "stars": (top_opp.get("recommendation") or {}).get("stars") if top_opp else None,
        }
    elif top_opp and top_opp.get("recommendation", {}).get("should_generate"):
        angle = top_opp.get("primary_angle") or "Educational"
        recommended_action = {
            "label": f"Generate LinkedIn post ({angle})",
            "action": "generate_post",
            "opportunity_id": top_opp["id"],
            "content_type": "educational",
            "primary_article_id": top_opp.get("primary_article_id"),
            "stars": top_opp.get("recommendation", {}).get("stars"),
        }

    suggested = top_opp["title"] if top_opp else "Capture a success story"
    if int(gaps.get("success_story") or 0) > int(gaps.get("educational") or 0):
        suggested = "Client success story"

    spacing_hint = None
    if top_opp and any(
        (o.get("duplicate") or {}).get("already_covered") for o in opportunities[:5]
    ):
        spacing_hint = "Space similar Microsoft/security themes — avoid posting the same angle two days in a row."

    return {
        "greeting": _greeting(),
        "narrative": narrative,
        "recommended_action": recommended_action,
        "memory": memory,
        "spacing_hint": spacing_hint,
        "briefing": {
            "articles_analysed": analysed,
            "opportunities": opp_n,
            "trends": trend_n,
            "high_priority": int(summary.get("high_priority") or 0),
            "recommended_today": int(summary.get("recommended_today") or 0),
            "already_scheduled": int(summary.get("already_scheduled") or 0),
            "needs_review": int(summary.get("needs_review") or 0),
            "average_opportunity_score": avg,
            "label": "estimated",
        },
        "strategic_goal": {
            "statement": goal_statement,
            "progress_pct": progress,
            "suggested_next_topic": suggested,
        },
        "generate_first": [
            {
                "id": o["id"],
                "title": o["title"],
                "score": o["opportunity_score"],
                "primary_article_id": o.get("primary_article_id"),
            }
            for o in (today or high or opportunities)[:4]
        ],
        "later": [
            {
                "id": o["id"],
                "title": o["title"],
                "score": o["opportunity_score"],
                "primary_article_id": o.get("primary_article_id"),
            }
            for o in later[:6]
        ],
        "plan_health": plan,
        "review_queue": summary.get("review_queue") or [],
        "estimates_label": "estimated",
    }


def clamp_mix(mix_pct: int, avg_score: int) -> int:
    if avg_score <= 0:
        return mix_pct
    return max(0, min(100, int(round(mix_pct * 0.7 + avg_score * 0.3))))
