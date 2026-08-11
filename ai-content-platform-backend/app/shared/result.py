"""Result pattern for expected business outcomes (not infrastructure failures)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Success(Generic[T]):
    value: T

    @property
    def is_success(self) -> bool:
        return True

    @property
    def is_failure(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    message: str

    @property
    def is_success(self) -> bool:
        return False

    @property
    def is_failure(self) -> bool:
        return True


Result = Success[T] | Failure


def ok(value: T) -> Success[T]:
    return Success(value)


def fail(code: str, message: str) -> Failure:
    return Failure(code=code, message=message)
