"""Durable aggregate provider budgets with concurrency-safe reservations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_UP

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.infrastructure.postgres.models.ai_ops import (
    ProviderBudget,
    ProviderBudgetReservation,
    ProviderConfig,
)
from app.infrastructure.postgres.session import async_session_factory

DEFAULT_MONTHLY_LIMIT_USD = Decimal("10.000000")
_ZERO = Decimal("0.000000")
_MONEY_PRECISION = Decimal("0.000001")


class ProviderBudgetExceeded(AppError):
    status_code = 402
    error_code = "PROVIDER_BUDGET_EXCEEDED"


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(max(0.0, float(value)))).quantize(
        _MONEY_PRECISION, rounding=ROUND_UP
    )


def _month_start(now: datetime | None = None) -> date:
    current = now or datetime.now(timezone.utc)
    return date(current.year, current.month, 1)


def _normalise_provider(provider: str) -> str:
    value = provider.strip().lower()
    # The UI calls this provider “OpenAI / GPT”; every GPT model shares this pot.
    return "openai" if value in {"gpt", "openai_gpt"} else value


@dataclass(frozen=True, slots=True)
class BudgetReservation:
    id: uuid.UUID
    amount_usd: Decimal
    provider: str


class ProviderBudgetService:
    """One monthly limit per provider, shared across all of its models."""

    async def _ensure_row(self, organization_id: uuid.UUID, provider: str) -> None:
        provider = _normalise_provider(provider)
        if not provider:
            return
        try:
            async with async_session_factory() as session:
                exists = (
                    await session.execute(
                        select(ProviderBudget.id).where(
                            ProviderBudget.organization_id == organization_id,
                            ProviderBudget.provider == provider,
                        )
                    )
                ).scalar_one_or_none()
                if exists is None:
                    session.add(
                        ProviderBudget(
                            organization_id=organization_id,
                            provider=provider,
                            monthly_limit_usd=DEFAULT_MONTHLY_LIMIT_USD,
                            month_start=_month_start(),
                            spent_usd=_ZERO,
                            is_enabled=True,
                        )
                    )
                    await session.commit()
        except IntegrityError:
            # Another concurrent request inserted the same unique provider row.
            return

    @staticmethod
    def _reset_month_if_needed(row: ProviderBudget) -> None:
        current = _month_start()
        if row.month_start != current:
            row.month_start = current
            row.spent_usd = _ZERO

    async def reserve(
        self,
        organization_id: uuid.UUID | str | None,
        *,
        provider: str,
        estimated_cost_usd: float,
        model: str | None = None,
    ) -> BudgetReservation | None:
        """Reserve against the provider's shared pot before a paid call."""
        del model  # Model is useful to call-site telemetry, not budget identity.
        if organization_id is None:
            return None
        try:
            org_id = (
                organization_id
                if isinstance(organization_id, uuid.UUID)
                else uuid.UUID(str(organization_id))
            )
        except ValueError:
            return None
        provider = _normalise_provider(provider)
        if not provider:
            return None
        estimate = _money(estimated_cost_usd)
        await self._ensure_row(org_id, provider)

        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            async with session.begin():
                row = (
                    await session.execute(
                        select(ProviderBudget)
                        .where(
                            ProviderBudget.organization_id == org_id,
                            ProviderBudget.provider == provider,
                        )
                        .with_for_update()
                    )
                ).scalar_one()
                self._reset_month_if_needed(row)
                await session.execute(
                    delete(ProviderBudgetReservation).where(
                        ProviderBudgetReservation.budget_id == row.id,
                        ProviderBudgetReservation.expires_at <= now,
                    )
                )
                reserved = (
                    await session.execute(
                        select(
                            func.coalesce(
                                func.sum(ProviderBudgetReservation.amount_usd), 0
                            )
                        ).where(
                            ProviderBudgetReservation.budget_id == row.id,
                            ProviderBudgetReservation.expires_at > now,
                        )
                    )
                ).scalar_one()
                spent = Decimal(row.spent_usd or 0)
                active_reserved = Decimal(reserved or 0)
                limit = Decimal(row.monthly_limit_usd or 0)
                if row.is_enabled and spent + active_reserved + estimate > limit:
                    remaining = max(_ZERO, limit - spent - active_reserved)
                    label = "OpenAI / GPT" if provider == "openai" else provider.title()
                    raise ProviderBudgetExceeded(
                        f"Monthly {label} budget reached. Remaining ${remaining:.2f}; "
                        f"this call reserves ${estimate:.2f}. Increase the provider "
                        "limit in Settings or wait until next month."
                    )
                reservation = ProviderBudgetReservation(
                    budget_id=row.id,
                    amount_usd=estimate,
                    expires_at=now + timedelta(minutes=15),
                )
                session.add(reservation)
                await session.flush()
                return BudgetReservation(reservation.id, estimate, provider)

    async def settle(
        self,
        reservation: BudgetReservation | None,
        *,
        actual_cost_usd: float,
    ) -> None:
        if reservation is None:
            return
        actual = _money(actual_cost_usd)
        async with async_session_factory() as session:
            async with session.begin():
                held = await session.get(ProviderBudgetReservation, reservation.id)
                if held is None:
                    return
                row = (
                    await session.execute(
                        select(ProviderBudget)
                        .where(ProviderBudget.id == held.budget_id)
                        .with_for_update()
                    )
                ).scalar_one()
                self._reset_month_if_needed(row)
                row.spent_usd = Decimal(row.spent_usd or 0) + actual
                await session.delete(held)

    async def cancel(self, reservation: BudgetReservation | None) -> None:
        if reservation is None:
            return
        async with async_session_factory() as session:
            async with session.begin():
                held = await session.get(ProviderBudgetReservation, reservation.id)
                if held is not None:
                    await session.delete(held)

    async def ensure_configured_providers(self, organization_id: uuid.UUID) -> None:
        async with async_session_factory() as session:
            configured = (
                await session.execute(
                    select(ProviderConfig.provider)
                    .where(ProviderConfig.organization_id == organization_id)
                    .distinct()
                )
            ).scalars().all()
        # These are the two paid providers supported by this delivery. Keep both
        # visible in Settings even before their keys are entered.
        providers = {"gemini", "openai"}
        providers.update(str(provider) for provider in configured if provider)
        for provider in providers:
            await self._ensure_row(organization_id, provider)

    async def list_for_org(self, organization_id: uuid.UUID) -> list[dict]:
        await self.ensure_configured_providers(organization_id)
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    select(ProviderBudget)
                    .where(ProviderBudget.organization_id == organization_id)
                    .order_by(ProviderBudget.provider)
                )
            ).scalars().all()
            result: list[dict] = []
            for row in rows:
                spent = (
                    _ZERO
                    if row.month_start != _month_start(now)
                    else Decimal(row.spent_usd or 0)
                )
                reserved = (
                    await session.execute(
                        select(
                            func.coalesce(
                                func.sum(ProviderBudgetReservation.amount_usd), 0
                            )
                        ).where(
                            ProviderBudgetReservation.budget_id == row.id,
                            ProviderBudgetReservation.expires_at > now,
                        )
                    )
                ).scalar_one()
                limit = Decimal(row.monthly_limit_usd or 0)
                committed = spent + Decimal(reserved or 0)
                remaining = max(_ZERO, limit - committed) if row.is_enabled else None
                result.append(
                    {
                        "provider": row.provider,
                        "display_name": (
                            "OpenAI / GPT"
                            if row.provider == "openai"
                            else row.provider.title()
                        ),
                        "monthly_limit_usd": float(limit),
                        "spent_usd": float(spent),
                        "reserved_usd": float(reserved or 0),
                        "remaining_usd": (
                            float(remaining) if remaining is not None else None
                        ),
                        "is_enabled": row.is_enabled,
                        "is_blocked": bool(row.is_enabled and committed >= limit),
                        "month_start": str(_month_start(now)),
                    }
                )
            return result

    async def update_limit(
        self,
        organization_id: uuid.UUID,
        *,
        provider: str,
        monthly_limit_usd: float,
        is_enabled: bool,
    ) -> dict:
        if monthly_limit_usd < 0 or monthly_limit_usd > 10_000:
            raise ValidationError("Monthly provider budget must be between $0 and $10,000")
        provider = _normalise_provider(provider)
        await self._ensure_row(organization_id, provider)
        async with async_session_factory() as session:
            async with session.begin():
                row = (
                    await session.execute(
                        select(ProviderBudget)
                        .where(
                            ProviderBudget.organization_id == organization_id,
                            ProviderBudget.provider == provider,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise NotFoundError("ProviderBudget", provider)
                self._reset_month_if_needed(row)
                row.monthly_limit_usd = _money(monthly_limit_usd)
                row.is_enabled = bool(is_enabled)
        rows = await self.list_for_org(organization_id)
        return next(row for row in rows if row["provider"] == provider)
