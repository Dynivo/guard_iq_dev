"""Inference backend abstraction for provider factory."""

from __future__ import annotations

from enum import Enum

from app.core.config import get_settings


class InferenceBackend(str, Enum):
    REMOTE = "remote"
    LOCAL = "local"
    GPU_CLUSTER = "gpu_cluster"


def resolve_inference_backend(provider_name: str) -> InferenceBackend:
    settings = get_settings()
    configured = getattr(settings, "INFERENCE_BACKEND", "remote").lower()
    if provider_name in {"ollama", "local", "vllm"}:
        if configured == InferenceBackend.GPU_CLUSTER.value:
            return InferenceBackend.GPU_CLUSTER
        return InferenceBackend.LOCAL
    if configured == InferenceBackend.LOCAL.value:
        return InferenceBackend.LOCAL
    if configured == InferenceBackend.GPU_CLUSTER.value:
        return InferenceBackend.GPU_CLUSTER
    return InferenceBackend.REMOTE
