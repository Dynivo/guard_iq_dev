"""Image replay store and diff service."""

from __future__ import annotations

from app.modules.image.domain.models import ImageDiff, ImagePipelineResult, ImageReplayRecord


class InMemoryImageReplayStore:
    def __init__(self) -> None:
        self._items: dict[str, ImageReplayRecord] = {}
        self._by_job: dict[str, ImageReplayRecord] = {}

    def save(self, record: ImageReplayRecord) -> None:
        self._items[record.replay_id] = record
        self._by_job[record.job_id] = record

    def get(self, replay_id: str) -> ImageReplayRecord | None:
        return self._items.get(replay_id)

    def get_by_job(self, job_id: str) -> ImageReplayRecord | None:
        return self._by_job.get(job_id)


class DefaultImageDiffService:
    def diff(self, left: ImagePipelineResult, right: ImagePipelineResult) -> ImageDiff:
        changes: dict = {}
        if left.prompt_hash != right.prompt_hash:
            changes["prompt_hash"] = {"left": left.prompt_hash, "right": right.prompt_hash}
        if left.workflow_id != right.workflow_id or left.workflow_version != right.workflow_version:
            changes["workflow"] = {
                "left": f"{left.workflow_id}@{left.workflow_version}",
                "right": f"{right.workflow_id}@{right.workflow_version}",
            }
        if left.provider != right.provider:
            changes["provider"] = {"left": left.provider, "right": right.provider}
        if left.quality_score != right.quality_score:
            changes["quality_score"] = {"left": left.quality_score, "right": right.quality_score}
        if left.seed != right.seed:
            changes["seed"] = {"left": left.seed, "right": right.seed}
        return ImageDiff(
            left_job_id=left.job_id,
            right_job_id=right.job_id,
            field_changes=changes,
            prompt_changed=left.prompt_hash != right.prompt_hash,
            workflow_changed=(left.workflow_id, left.workflow_version)
            != (right.workflow_id, right.workflow_version),
            provider_changed=left.provider != right.provider,
        )
