"""BudgetTracker — per-session LLM spend guard.

Backed by Redis (INCRBYFLOAT for atomic increments). Exposes the current
BudgetStage which controls model tier selection in LLMFactory.

See LLM_DEGRADATION.md Section 1 for the threshold table.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .features import BudgetStage

logger = logging.getLogger(__name__)

_CAUTION_USD  = 3.00
_CRITICAL_USD = 4.50
_LIMIT_USD    = 5.00


@dataclass
class BudgetTracker:
    session_id:  str
    _spent_usd:  float = field(default=0.0, repr=False)
    _limit_usd:  float = field(default=_LIMIT_USD, repr=False)

    # TODO(sprint1): inject Redis client here and load/persist via INCRBYFLOAT
    # For now the tracker is in-memory — sufficient for single-process testing.

    @classmethod
    async def load(cls, session_id: str, redis: object | None = None) -> "BudgetTracker":
        """Load current spend from Redis. Falls back to 0.0 if key missing."""
        spent = 0.0
        if redis is not None:
            # TODO: raw = await redis.get(f"budget:session:{session_id}")
            # spent = float(raw or 0.0)
            pass
        return cls(session_id=session_id, _spent_usd=spent)

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    def stage(self) -> BudgetStage:
        if self._spent_usd >= self._limit_usd:
            return BudgetStage.EXHAUSTED
        if self._spent_usd >= _CRITICAL_USD:
            return BudgetStage.CRITICAL
        if self._spent_usd >= _CAUTION_USD:
            return BudgetStage.CAUTION
        return BudgetStage.NORMAL

    def is_exhausted(self) -> bool:
        return self.stage() == BudgetStage.EXHAUSTED

    async def record(self, cost_usd: float, redis: object | None = None) -> None:
        """Atomically increment spend. Writes to Redis and updates in-memory counter."""
        self._spent_usd += cost_usd
        if redis is not None:
            # TODO: await redis.incrbyfloat(f"budget:session:{self.session_id}", cost_usd)
            pass
        if self.stage() in (BudgetStage.CAUTION, BudgetStage.CRITICAL):
            logger.warning(
                "Session %s budget stage: %s ($%.4f / $%.2f)",
                self.session_id, self.stage(), self._spent_usd, self._limit_usd,
            )
