from __future__ import annotations

import pytest

from scripts.reset_admin_password import validate_recovery_password


def test_recovery_password_validation_accepts_strong_match() -> None:
    assert validate_recovery_password("correct horse battery", "correct horse battery") == (
        "correct horse battery"
    )


@pytest.mark.parametrize(
    ("password", "confirmation", "message"),
    [
        ("long-enough-password", "different-password", "do not match"),
        ("too-short", "too-short", "at least 12"),
        ("x" * 73, "x" * 73, "72 UTF-8 bytes"),
    ],
)
def test_recovery_password_validation_rejects_invalid_input(
    password: str, confirmation: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_recovery_password(password, confirmation)
