"""Multimodal visual creative critic — scores Gemini outputs via chat provider."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.design_spec import VisualDesignSpec

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _quality_cfg() -> dict[str, Any]:
    return load_yaml("quality_rules.yaml")


@dataclass(slots=True)
class CriticResult:
    overall: float
    scores: dict[str, float] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)
    passed: bool = True
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "scores": dict(self.scores),
            "issues": list(self.issues),
            "recommendations": list(self.recommendations),
            "flags": dict(self.flags),
            "passed": self.passed,
            "raw": dict(self.raw),
        }


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def _heuristic_critic(spec: VisualDesignSpec) -> CriticResult:
    """Deterministic fallback when LLM critic is disabled or fails."""
    scores = {
        "composition": 78.0,
        "legibility": 80.0,
        "brand_alignment": 82.0,
        "factual_fidelity": 85.0 if spec.factual_constraints else 75.0,
        "density": 76.0,
        "logo": 70.0 if spec.logo.enabled else 90.0,
    }
    overall = round(sum(scores.values()) / len(scores), 2)
    return CriticResult(
        overall=overall,
        scores=scores,
        issues=[],
        recommendations=[],
        flags={"logo_ok": not spec.logo.enabled},
        passed=True,
        raw={"mode": "heuristic"},
    )


class VisualCreativeCritic:
    """Scores image bytes against design constraints via configurable chat provider."""

    def __init__(self, chat_complete: Any | None = None) -> None:
        self._chat_complete = chat_complete

    def enabled_for_mode(self, creative_mode: str) -> bool:
        settings = get_settings()
        mode = (creative_mode or "").lower()
        if mode in {"gemini_infographic", "gemini_creative"}:
            # Default true for gemini modes unless explicitly disabled
            return bool(getattr(settings, "IMAGE_VISUAL_CRITIC_ENABLED", True))
        return bool(getattr(settings, "IMAGE_VISUAL_CRITIC_ENABLED", False))

    def threshold(self) -> float:
        settings = get_settings()
        # Prefer settings; quality_rules critic.min_overall is legacy 0–10 scale
        thr = float(getattr(settings, "IMAGE_QUALITY_THRESHOLD", 82.0) or 82.0)
        if thr <= 10:
            thr = thr * 10.0
        return thr

    def max_retries(self) -> int:
        settings = get_settings()
        return max(0, int(getattr(settings, "IMAGE_MAX_RETRIES", 2) or 0))

    async def critique(
        self,
        image_bytes: bytes,
        spec: VisualDesignSpec,
        *,
        brand: dict[str, Any] | None = None,
    ) -> CriticResult:
        brand = brand or {}
        if not image_bytes:
            return CriticResult(
                overall=0.0,
                scores={},
                issues=["empty_image"],
                recommendations=["Regenerate with a complete infographic layout."],
                flags={"logo_ok": False},
                passed=False,
                raw={"mode": "empty"},
            )

        if self._chat_complete is None:
            try:
                from app.infrastructure.llm.base import CompletionRequest
                from app.modules.providers.infrastructure.provider_factory import (
                    DefaultProviderFactory,
                )

                settings = get_settings()
                provider = DefaultProviderFactory().create(
                    str(getattr(settings, "DEFAULT_LLM_PROVIDER", None) or "gemini")
                )

                async def _complete(req: CompletionRequest) -> Any:
                    return await provider.complete(req)

                self._chat_complete = _complete
            except Exception as exc:  # noqa: BLE001
                logger.warning("visual_critic_provider_unavailable: %s", exc)
                result = _heuristic_critic(spec)
                result.passed = result.overall >= self.threshold()
                return result

        from app.infrastructure.llm.base import CompletionRequest

        facts = list(spec.factual_constraints)[:12]
        prompt = (
            "You are a LinkedIn creative QA critic for cybersecurity brand visuals.\n"
            "Score the attached image 0-100. Return JSON only with keys:\n"
            "overall (number), scores (object with composition,legibility,brand_alignment,"
            "factual_fidelity,density,logo), issues (string[]), recommendations (string[]),"
            "flags (object with logo_ok boolean).\n"
            f"Archetype: {spec.design_archetype}. Theme: {spec.brand_variant}.\n"
            f"Brand colors: primary={brand.get('primary_color') or spec.brand.primary}, "
            f"accent={brand.get('accent_color') or spec.brand.accent}.\n"
            f"Factual constraints (must appear correctly if text is present):\n"
            + "\n".join(f"- {f}" for f in facts)
            + "\nPenalize misspellings, empty sparse posters, neon glow, duplicated logos, "
            "and invented metrics."
        )

        # Many chat adapters are text-only; pass image as base64 hint in prompt metadata.
        b64 = base64.b64encode(image_bytes[:350_000]).decode("ascii")
        rich_prompt = (
            f"{prompt}\n\nIMAGE_PNG_BASE64_PREFIX (truncated for transport):\n{b64[:8000]}..."
        )

        try:
            completion = await self._chat_complete(
                CompletionRequest(
                    prompt=rich_prompt,
                    system_message="Return valid JSON only. No markdown.",
                    temperature=0.1,
                    max_tokens=800,
                    response_format="json",
                )
            )
            text = getattr(completion, "text", None) or str(completion)
            data = _extract_json(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("visual_critic_llm_failed: %s", exc)
            result = _heuristic_critic(spec)
            result.passed = result.overall >= self.threshold()
            return result

        if not data:
            result = _heuristic_critic(spec)
            result.passed = result.overall >= self.threshold()
            return result

        overall = float(data.get("overall") or 0)
        if overall <= 10:
            overall *= 10.0
        scores_raw = data.get("scores") or {}
        scores = {str(k): float(v) for k, v in scores_raw.items()} if isinstance(scores_raw, dict) else {}
        issues = [str(x) for x in (data.get("issues") or []) if str(x).strip()]
        recs = [str(x) for x in (data.get("recommendations") or []) if str(x).strip()]
        flags_raw = data.get("flags") if isinstance(data.get("flags"), dict) else {}
        flags = {str(k): bool(v) for k, v in flags_raw.items()}
        passed = overall >= self.threshold()
        return CriticResult(
            overall=round(overall, 2),
            scores=scores,
            issues=issues,
            recommendations=recs,
            flags=flags,
            passed=passed,
            raw=data,
        )
