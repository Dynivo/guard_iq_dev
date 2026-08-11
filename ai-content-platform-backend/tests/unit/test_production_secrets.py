"""Production JWT secret validation."""

from __future__ import annotations

import pytest

from app.core.config.settings import Settings


def test_production_rejects_default_jwt_secrets() -> None:
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="CHANGE-ME",
        JWT_REFRESH_SECRET_KEY="CHANGE-ME-REFRESH",
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        settings.validate_production_secrets()


def test_development_allows_default_jwt_secrets() -> None:
    settings = Settings(
        APP_ENV="development",
        JWT_SECRET_KEY="CHANGE-ME",
        JWT_REFRESH_SECRET_KEY="CHANGE-ME-REFRESH",
    )
    settings.validate_production_secrets()  # does not raise
