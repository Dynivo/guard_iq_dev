"""Optional AsyncSession binding for in-process event handlers (same UoW)."""

from __future__ import annotations

from contextvars import ContextVar, Token

from sqlalchemy.ext.asyncio import AsyncSession

_event_session: ContextVar[AsyncSession | None] = ContextVar("event_session", default=None)


def get_event_session() -> AsyncSession | None:
    return _event_session.get()


def set_event_session(session: AsyncSession) -> Token[AsyncSession | None]:
    return _event_session.set(session)


def reset_event_session(token: Token[AsyncSession | None]) -> None:
    _event_session.reset(token)
