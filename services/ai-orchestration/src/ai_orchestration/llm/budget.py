"""BudgetTracker — per-session LLM spend guard.

Backed by Redis (INCRBYFLOAT for atomic increments across concurrent workers).
Also maintains an in-memory counter so the BudgetStage is available without a
round-trip on every .stage() call.

Redis key schema (from REDIS_SCHEMA.md):
  budget:{workspace_id}:{session_id}:total_usd   — INCRBYFLOAT, 7-day TTL
  budget:{workspace_id}:{session_id}:stage        — string, 60-s TTL (cached tier)

If workspace_id is not provided (tests), falls back to:
  budget:{session_id}:total_usd

See docs/sprints/sprint0/DECISIONS.md §Budget for the threshold table.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .features import BudgetStage

logger = logging.getLogger(__name__)

_CAUTION_USD  = 3.00
_CRITICAL_USD = 4.50
_LIMIT_USD    = 5.00

_BUDGET_KEY_TTL = 7 * 24 * 3600  # 7 days in seconds


def _budget_key(session_id: str, workspace_id: str | None) -> str:
    if workspace_id:
        return f"budget:{workspace_id}:{session_id}:total_usd"
    return f"budget:{session_id}:total_usd"


@dataclass
class BudgetTracker:
    session_id:   str
    workspace_id: str | None = None
    _spent_usd:   float = field(default=0.0, repr=False)
    _limit_usd:   float = field(default=_LIMIT_USD, repr=False)

    @classmethod
    async def load(
        cls,
        session_id: str,
        redis: Any | None = None,
        workspace_id: str | None = None,
    ) -> "BudgetTracker":
        """Load current spend from Redis. Falls back to 0.0 if key missing or Redis unavailable."""
        spent = 0.0
        if redis is not None:
            try:
                raw = await redis.get(_budget_key(session_id, workspace_id))
                spent = float(raw or 0.0)
            except Exception:
                logger.warning(
                    "Failed to load budget from Redis for session %s — starting at 0.0",
                    session_id,
                )
        return cls(session_id=session_id, workspace_id=workspace_id, _spent_usd=spent)

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

    async def record(self, cost_usd: float, redis: Any | None = None) -> None:
        """Atomically increment spend. Updates in-memory counter and persists to Redis."""
        self._spent_usd += cost_usd

        if redis is not None:
            try:
                key = _budget_key(self.session_id, self.workspace_id)
                await redis.incrbyfloat(key, cost_usd)
                await redis.expire(key, _BUDGET_KEY_TTL)
            except Exception:
                logger.warning(
                    "Failed to persist budget increment to Redis (session=%s, cost=%.6f)",
                    self.session_id,
                    cost_usd,
                )

        stage = self.stage()
        if stage in (BudgetStage.CAUTION, BudgetStage.CRITICAL):
            logger.warning(
                "Session %s budget stage: %s ($%.4f / $%.2f)",
                self.session_id,
                stage,
                self._spent_usd,
                self._limit_usd,
            )
        elif stage == BudgetStage.EXHAUSTED:
            logger.error(
                "Session %s budget EXHAUSTED ($%.4f >= $%.2f)",
                self.session_id,
                self._spent_usd,
                self._limit_usd,
            )
