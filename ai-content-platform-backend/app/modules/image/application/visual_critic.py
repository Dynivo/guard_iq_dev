"""Multimodal visual creative critic — scores the actual generated image."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.image.application.config_loader import load_yaml
from app.modules.image.domain.design_spec import VisualDesignSpec
from app.modules.ai.application.cost import YamlCostEstimator
from app.modules.ai.application.provider_budgets import ProviderBudgetService

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

    def __init__(
        self,
        chat_complete: Any | None = None,
        multimodal_complete: Any | None = None,
    ) -> None:
        self._chat_complete = chat_complete
        self._multimodal_complete = multimodal_complete

    async def _complete_with_gemini(
        self,
        prompt: str,
        image_bytes: bytes,
        organization_id: Any | None = None,
    ) -> str:
        """Send the PNG as a real image part through the official Gemini SDK."""
        from google import genai
        from google.genai import types

        settings = get_settings()
        key = str(getattr(settings, "GEMINI_API_KEY", "") or "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is required for visual quality review")
        model = str(
            getattr(settings, "GEMINI_VISUAL_CRITIC_MODEL", "")
            or "gemini-flash-latest"
        )
        budgets = ProviderBudgetService()
        # Image tokenisation varies by vendor/model. Reserve a deliberately
        # conservative amount, then settle using response token counts.
        reservation = await budgets.reserve(
            organization_id,
            provider="gemini",
            model=model,
            estimated_cost_usd=0.01,
        )
        client = genai.Client(api_key=key)
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=800,
                    response_mime_type="application/json",
                ),
            )
        except Exception:
            await budgets.cancel(reservation)
            raise
        usage = getattr(response, "usage_metadata", None)
        tokens_in = int(getattr(usage, "prompt_token_count", 0) or 0)
        tokens_out = int(getattr(usage, "candidates_token_count", 0) or 0)
        actual = YamlCostEstimator().estimate(
            provider="gemini",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        await budgets.settle(
            reservation,
            actual_cost_usd=actual if tokens_in or tokens_out else 0.01,
        )
        return str(getattr(response, "text", "") or "")

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
        organization_id: Any | None = None,
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

        try:
            if self._multimodal_complete is not None:
                text = await self._multimodal_complete(prompt, image_bytes)
            elif self._chat_complete is not None:
                # Backwards-compatible injection point for unit/integration
                # callers. Production uses the true multimodal path above.
                from app.infrastructure.llm.base import CompletionRequest

                completion = await self._chat_complete(
                    CompletionRequest(
                        prompt=prompt,
                        system_message="Return valid JSON only. No markdown.",
                        temperature=0.1,
                        max_tokens=800,
                        response_format="json",
                    )
                )
                text = getattr(completion, "text", None) or str(completion)
            else:
                text = await self._complete_with_gemini(
                    prompt,
                    image_bytes,
                    organization_id=organization_id,
                )
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
