"""Analytics and cost-control API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderBudgetUpdateRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    monthly_limit_usd: float = Field(ge=0, le=10_000)
    is_enabled: bool = True
