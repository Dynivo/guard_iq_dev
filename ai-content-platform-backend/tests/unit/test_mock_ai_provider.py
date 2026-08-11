"""Unit tests for MockAIProvider JSON parsing and deterministic output."""

from __future__ import annotations

import json

import pytest

from app.infrastructure.llm.base import CompletionRequest
from app.infrastructure.llm.mock_adapter import MockAIProvider


@pytest.fixture
def provider() -> MockAIProvider:
    return MockAIProvider()


class TestMockAIProviderRelevance:
    """Tests for relevance scoring responses."""

    @pytest.mark.asyncio
    async def test_relevance_response_is_valid_json(self, provider: MockAIProvider) -> None:
        request = CompletionRequest(
            prompt="Score the relevance of this article about cybersecurity",
            model="mock-v1",
        )
        result = await provider.complete(request)
        data = json.loads(result.text)

        assert "relevant" in data
        assert "score" in data
        assert "sector" in data
        assert "framework" in data
        assert "audience" in data
        assert "angle" in data
        assert "reason" in data

    @pytest.mark.asyncio
    async def test_relevance_score_in_range(self, provider: MockAIProvider) -> None:
        request = CompletionRequest(
            prompt="Score this article relevance for the client",
            model="mock-v1",
        )
        result = await provider.complete(request)
        data = json.loads(result.text)

        assert 1 <= data["score"] <= 5
        assert isinstance(data["relevant"], bool)
        assert data["relevant"] == (data["score"] >= 3)

    @pytest.mark.asyncio
    async def test_relevance_sector_values(self, provider: MockAIProvider) -> None:
        request = CompletionRequest(
            prompt="Score relevance of healthcare data breach article",
            model="mock-v1",
        )
        result = await provider.complete(request)
        data = json.loads(result.text)

        valid_sectors = {"care", "healthcare", "legal", "accountancy", "cross-sector"}
        assert data["sector"] in valid_sectors

    @pytest.mark.asyncio
    async def test_deterministic_output(self, provider: MockAIProvider) -> None:
        """Same prompt produces same output."""
        request = CompletionRequest(
            prompt="Score the relevance of DSPT deadline article",
            model="mock-v1",
        )
        result1 = await provider.complete(request)
        result2 = await provider.complete(request)

        assert result1.text == result2.text


class TestMockAIProviderContent:
    """Tests for content generation responses."""

    @pytest.mark.asyncio
    async def test_content_response_is_valid_json(self, provider: MockAIProvider) -> None:
        request = CompletionRequest(
            prompt="Generate a LinkedIn post about managed services",
            model="mock-v1",
        )
        result = await provider.complete(request)
        data = json.loads(result.text)

        assert "hook" in data
        assert "body" in data
        assert "cta" in data
        assert "hashtags" in data
        assert "variations" in data

    @pytest.mark.asyncio
    async def test_content_has_variations(self, provider: MockAIProvider) -> None:
        request = CompletionRequest(
            prompt="Generate content for a LinkedIn post about compliance",
            model="mock-v1",
        )
        result = await provider.complete(request)
        data = json.loads(result.text)

        assert isinstance(data["variations"], list)
        assert len(data["variations"]) >= 2
        for variation in data["variations"]:
            assert "hook" in variation
            assert "body" in variation

    @pytest.mark.asyncio
    async def test_content_hashtags_are_list(self, provider: MockAIProvider) -> None:
        request = CompletionRequest(
            prompt="Generate LinkedIn content about phishing awareness",
            model="mock-v1",
        )
        result = await provider.complete(request)
        data = json.loads(result.text)

        assert isinstance(data["hashtags"], list)
        assert len(data["hashtags"]) >= 3
        for tag in data["hashtags"]:
            assert tag.startswith("#")

    @pytest.mark.asyncio
    async def test_result_metadata(self, provider: MockAIProvider) -> None:
        request = CompletionRequest(
            prompt="Generate post content",
            model="mock-v1",
            correlation_id="test-123",
        )
        result = await provider.complete(request)

        assert result.provider == "mock"
        assert result.model == "mock-v1"
        assert result.latency_ms >= 0
        assert result.tokens_in > 0
        assert result.tokens_out > 0
        assert result.cost_estimate == 0.0
