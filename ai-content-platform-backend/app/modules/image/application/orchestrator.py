"""Image orchestrator — retries, fallback workflows, provider selection, metrics."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.image.application.config_loader import load_yaml
from app.modules.image.application.metrics import ImageMetricsSnapshot, InMemoryImageMetrics
from app.modules.image.domain.models import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImagePromptRequest,
)
from app.modules.image.domain.ports import ImageProvider

logger = get_logger(__name__)


class DefaultImageOrchestrator:
    def __init__(
        self,
        provider: ImageProvider,
        *,
        config_dir: Path | None = None,
        metrics: InMemoryImageMetrics | None = None,
        provider_factory: Callable[[str], ImageProvider] | None = None,
    ) -> None:
        self._provider = provider
        self._cfg = load_yaml("orchestrator.yaml", config_dir)
        self._metrics = metrics or InMemoryImageMetrics()
        self._provider_factory = provider_factory

    async def execute(
        self, prompt_request: ImagePromptRequest, *, logo_bytes: bytes | None = None
    ) -> ImageGenerationResult:
        max_attempts = max(1, int(self._cfg.get("max_attempts") or 2))
        fallbacks = list(self._cfg.get("fallback_workflow_ids") or [])
        workflow_chain = [prompt_request.workflow_id, *[w for w in fallbacks if w != prompt_request.workflow_id]]
        queue_started = time.perf_counter()
        retries = 0
        failures = 0
        last_error: Exception | None = None

        for wf_id in workflow_chain:
            for attempt in range(1, max_attempts + 1):
                queue_ms = int((time.perf_counter() - queue_started) * 1000)
                req = ImageGenerationRequest.from_prompt_request(
                    ImagePromptRequest(
                        positive_prompt=prompt_request.positive_prompt,
                        negative_prompt=prompt_request.negative_prompt,
                        width=prompt_request.width,
                        height=prompt_request.height,
                        style=prompt_request.style,
                        workflow_id=wf_id,
                        workflow_version=prompt_request.workflow_version,
                        seed=prompt_request.seed,
                        parameters=dict(prompt_request.parameters),
                        metadata=dict(prompt_request.metadata),
                    ),
                    logo_bytes=logo_bytes,
                )
                try:
                    result = await self._provider.generate(req)
                    snap = ImageMetricsSnapshot(
                        generation_time_ms=result.latency_ms,
                        queue_time_ms=queue_ms,
                        retries=retries,
                        failures=failures,
                        provider_usage={result.provider: 1},
                        workflow_version=f"{wf_id}@{prompt_request.workflow_version}",
                    )
                    self._metrics.record(snap)
                    result.workflow_id = wf_id
                    result.workflow_version = prompt_request.workflow_version
                    result.metadata = {
                        **result.metadata,
                        "queue_time_ms": queue_ms,
                        "retry_count": retries,
                        "attempt": attempt,
                    }
                    return result
                except Exception as exc:  # noqa: BLE001 — orchestrator boundary
                    failures += 1
                    retries += 1
                    last_error = exc
                    logger.warning(
                        "image_generate_failed",
                        extra={"workflow_id": wf_id, "attempt": attempt, "error": str(exc)},
                    )

        self._metrics.record(
            ImageMetricsSnapshot(retries=retries, failures=failures, queue_time_ms=0)
        )
        raise AppError(f"Image generation failed after retries: {last_error}") from last_error
