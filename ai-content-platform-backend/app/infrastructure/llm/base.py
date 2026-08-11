"""LLM provider base — re-exports canonical shared types for adapters."""

from __future__ import annotations

from app.shared.ai_types import AIProvider, CompletionRequest, CompletionResult

__all__ = ["AIProvider", "CompletionRequest", "CompletionResult"]
