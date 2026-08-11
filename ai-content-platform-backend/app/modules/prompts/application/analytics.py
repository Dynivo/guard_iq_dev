"""In-memory Prompt Analytics — approval/failure rates, token efficiency."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.prompts.domain.models import EvalRunResult, PromptRequest


@dataclass
class PromptAnalytics:
    builds: int = 0
    build_failures: int = 0
    total_tokens: int = 0
    eval_runs: int = 0
    eval_passes: int = 0
    scores: list[float] = field(default_factory=list)

    def record_build(self, request: PromptRequest) -> None:
        self.builds += 1
        self.total_tokens += int(request.token_estimate or 0)
        if not request.valid:
            self.build_failures += 1

    def record_eval(self, results: list[EvalRunResult]) -> None:
        for r in results:
            self.eval_runs += 1
            self.scores.append(r.score)
            if r.passed:
                self.eval_passes += 1

    def snapshot(self) -> dict[str, Any]:
        avg_score = sum(self.scores) / len(self.scores) if self.scores else 0.0
        avg_tokens = self.total_tokens / self.builds if self.builds else 0.0
        return {
            "builds": self.builds,
            "build_failures": self.build_failures,
            "approval_rate": (
                (self.builds - self.build_failures) / self.builds if self.builds else 0.0
            ),
            "failure_rate": (
                self.build_failures / self.builds if self.builds else 0.0
            ),
            "eval_runs": self.eval_runs,
            "eval_pass_rate": (
                self.eval_passes / self.eval_runs if self.eval_runs else 0.0
            ),
            "quality_score": avg_score,
            "token_efficiency": avg_tokens,
        }
