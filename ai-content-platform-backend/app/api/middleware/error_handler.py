"""Global error-handling middleware.

Maps AppError subclasses to HTTP responses with the standard envelope
format.  Catches unhandled exceptions and returns a generic 500.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.schemas.envelope import error_response
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.state.request_id if hasattr(request.state, "request_id") else ""
        try:
            return await call_next(request)
        except AppError as exc:
            logger.warning(
                "AppError: status=%d code=%s message=%s request_id=%s",
                exc.status_code,
                exc.error_code,
                exc.message,
                request_id,
            )
            return ORJSONResponse(
                status_code=exc.status_code,
                content=error_response(exc.message, request_id),
            )
        except Exception as exc:
            error_id = str(uuid.uuid4())[:8]
            logger.exception(
                "Unhandled exception: error_id=%s request_id=%s", error_id, request_id
            )
            return ORJSONResponse(
                status_code=500,
                content=error_response(
                    f"Internal server error (ref: {error_id})", request_id
                ),
            )
