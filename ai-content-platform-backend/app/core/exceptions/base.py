"""Application error hierarchy with deterministic HTTP status mapping.

Every domain/application error inherits from AppError.  The error-handler
middleware maps each subclass to the correct HTTP status code automatically,
keeping route handlers free of HTTP-level error logic.
"""

from __future__ import annotations


class AppError(Exception):
    """Base application error.  All custom errors extend this."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        self.message = message
        super().__init__(self.message)


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, resource: str = "Resource", identifier: str = "") -> None:
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(detail)


class AuthenticationError(AppError):
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"

    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(message)


class AuthorizationError(AppError):
    status_code = 403
    error_code = "AUTHORIZATION_ERROR"

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"

    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message)
