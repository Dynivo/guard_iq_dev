"""Password hashing via passlib bcrypt.

CryptContext is synchronous but bcrypt is intentionally slow (hashing
takes ~200 ms).  For the auth-login path this is acceptable; if needed
later the hash/verify calls can be wrapped with run_in_executor.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return the bcrypt hash of a plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return _pwd_context.verify(plain, hashed)
