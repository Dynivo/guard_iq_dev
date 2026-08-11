"""Learning confidence metrics — usage / success tracking on artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class LearningConfidenceService:
    """Update confidence-related counters without Analytics dashboards."""

    def record_usage(
        self,
        artifact: dict[str, Any],
        *,
        success: bool | None = None,
    ) -> dict[str, Any]:
        artifact = dict(artifact)
        artifact["usage_count"] = int(artifact.get("usage_count") or 0) + 1
        artifact["last_used"] = datetime.now(timezone.utc).isoformat()
        if success is not None:
            # Incremental success_rate: running mean over usage_count
            prev_rate = float(artifact.get("success_rate") or 0.0)
            n = int(artifact["usage_count"])
            prev_successes = prev_rate * (n - 1)
            if success:
                prev_successes += 1
            artifact["success_rate"] = round(prev_successes / n, 4)
        return artifact

    def record_approval(self, artifact: dict[str, Any]) -> dict[str, Any]:
        artifact = dict(artifact)
        artifact["approval_count"] = int(artifact.get("approval_count") or 0) + 1
        # Slight confidence bump capped at 1.0
        conf = float(artifact.get("confidence") or 0.5)
        artifact["confidence"] = min(1.0, round(conf + 0.05, 4))
        return artifact
