"""Retry delay calculation."""

from __future__ import annotations

import asyncio

from app.modules.workflow.domain.models import RetryPolicy, RetryStrategy


def compute_delay_ms(policy: RetryPolicy, attempt_number: int) -> int:
    """attempt_number is 1-based for the attempt that just failed."""
    if policy.strategy == RetryStrategy.NONE:
        return 0
    if policy.strategy == RetryStrategy.FIXED_DELAY:
        return max(0, policy.delay_ms)
    if policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        delay = policy.delay_ms * (2 ** max(0, attempt_number - 1))
        return min(delay, policy.max_delay_ms)
    return 0


async def sleep_before_retry(policy: RetryPolicy, attempt_number: int) -> None:
    delay = compute_delay_ms(policy, attempt_number)
    if delay > 0:
        await asyncio.sleep(delay / 1000.0)


def should_retry(policy: RetryPolicy, attempts_used: int) -> bool:
    return attempts_used < max(1, policy.max_attempts)
