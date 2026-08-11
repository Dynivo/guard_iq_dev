"""Middleware that assigns a unique request/correlation ID to every request."""

from __future__ import annotations

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.observability.correlation import (
    reset_correlation_id,
    reset_organization_id,
    set_correlation_id,
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        corr_token = set_correlation_id(request_id)
        org_token = None
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = request_id
            return response
        finally:
            reset_correlation_id(corr_token)
            if org_token is not None:
                reset_organization_id(org_token)
