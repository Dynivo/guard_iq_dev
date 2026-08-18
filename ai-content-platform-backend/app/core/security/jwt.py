"""JWT token creation and verification.

Uses PyJWT with HMAC-SHA256 for stateless authentication.
Access and refresh tokens have separate secrets so a leaked access
token cannot mint refresh tokens and vice versa.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Create a short-lived access JWT."""
    settings = get_settings()
    expire = _now_utc() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    claims: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh JWT."""
    settings = get_settings()
    expire = _now_utc() + timedelta(minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES)
    claims: dict[str, Any] = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(claims, settings.JWT_REFRESH_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, token_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT.  Raises AuthenticationError on failure."""
    settings = get_settings()
    secret = (
        settings.JWT_SECRET_KEY if token_type == "access" else settings.JWT_REFRESH_SECRET_KEY
    )
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise AuthenticationError("Token is invalid or expired") from exc

    if payload.get("type") != token_type:
        raise AuthenticationError(f"Expected {token_type} token")

    return payload
