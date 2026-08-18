"""Regression coverage for static article routes shadowed by article IDs."""

from __future__ import annotations

from app.main import create_app


def test_screening_status_route_precedes_generic_article_route() -> None:
    app = create_app()
    # FastAPI 0.116+ stores included routers lazily, while OpenAPI preserves
    # the effective path registration order used for route matching.
    paths = list(app.openapi()["paths"])

    assert paths.index("/api/v1/articles/screening-status") < paths.index(
        "/api/v1/articles/{article_id}"
    )
