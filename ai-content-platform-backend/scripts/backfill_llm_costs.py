"""Reprice historical llm_calls.cost_estimate from tokens using corrected pricing.yaml.

Usage (from backend venv):
  python scripts/backfill_llm_costs.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select


async def main() -> None:
    from app.infrastructure.postgres.models.ai_ops import LlmCall
    from app.infrastructure.postgres.session import async_session_factory
    from app.modules.ai.application.cost import YamlCostEstimator

    estimator = YamlCostEstimator()
    async with async_session_factory() as session:
        rows = (await session.execute(select(LlmCall))).scalars().all()
        updated = 0
        old_total = 0.0
        for row in rows:
            old_total += float(row.cost_estimate or 0.0)
            tin = int(row.tokens_in or 0)
            tout = int(row.tokens_out or 0)
            if tin == 0 and tout == 0:
                if float(row.cost_estimate or 0.0) > 1.0:
                    row.cost_estimate = 0.0
                    updated += 1
                continue
            new = estimator.estimate(
                provider=str(row.provider or "openai"),
                model=str(row.model or "default"),
                tokens_in=tin,
                tokens_out=tout,
            )
            if abs(float(row.cost_estimate or 0.0) - new) > 1e-9:
                row.cost_estimate = new
                updated += 1

        await session.commit()
        new_total = sum(float(r.cost_estimate or 0.0) for r in rows)
        print(
            f"Repriced {updated}/{len(rows)} llm_calls. "
            f"old_total=${old_total:.6f} → new_total=${new_total:.6f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
