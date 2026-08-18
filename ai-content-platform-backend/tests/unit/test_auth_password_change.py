from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from app.core.exceptions import AuthenticationError, ValidationError
from app.core.security.password import hash_password, verify_password
from app.modules.auth.application.use_cases import ChangePasswordUseCase
from app.modules.auth.domain.records import UserRecord


class FakeUserRepository:
    def __init__(self, user: UserRecord) -> None:
        self.user = user

    async def get_by_id(self, user_id: uuid.UUID) -> UserRecord | None:
        return self.user if self.user.id == user_id else None

    async def update_password(self, user_id: uuid.UUID, hashed_password: str) -> None:
        assert user_id == self.user.id
        self.user = replace(self.user, password_hash=hashed_password)


def _user(password: str = "original-password") -> UserRecord:
    return UserRecord(
        id=uuid.uuid4(),
        email="admin@guardiq.com",
        display_name="Admin",
        password_hash=hash_password(password),
        is_active=True,
        organization_id=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_change_password_verifies_current_and_hashes_replacement() -> None:
    user = _user()
    repo = FakeUserRepository(user)

    await ChangePasswordUseCase(repo).execute(
        user.id,
        current_password="original-password",
        new_password="new-unique-password",
    )

    assert verify_password("new-unique-password", repo.user.password_hash)
    assert not verify_password("original-password", repo.user.password_hash)


@pytest.mark.asyncio
async def test_change_password_rejects_incorrect_current_password() -> None:
    user = _user()
    repo = FakeUserRepository(user)

    with pytest.raises(AuthenticationError, match="Current password is incorrect"):
        await ChangePasswordUseCase(repo).execute(
            user.id,
            current_password="wrong-password",
            new_password="new-unique-password",
        )


@pytest.mark.asyncio
async def test_change_password_rejects_reuse() -> None:
    user = _user()
    repo = FakeUserRepository(user)

    with pytest.raises(ValidationError, match="must be different"):
        await ChangePasswordUseCase(repo).execute(
            user.id,
            current_password="original-password",
            new_password="original-password",
        )
