"""SessionLLMContext and SessionLLMContextFactory.

One context is created per turn. It carries:
  - The immutable session state from Rust (or a dict for tests)
  - A BudgetTracker scoped to the session
  - Lazy LLM client slots keyed by LLMFeature
  - A token_sink queue for streaming tokens to the gRPC servicer

The factory is a process-level singleton injected at startup.

See LLM_DESIGN_PATTERNS.md for the full design.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from ..config import OrchestrationConfig
from .budget import BudgetTracker
from .factory import LLMFactory
from .features import BudgetStage, LLMFeature

logger = logging.getLogger(__name__)


@dataclass
class SessionLLMContext:
    """Per-turn context. Holds lazy LLM client slots, budget tracker, and token sink."""

    session_state: Any              # SessionStateProto from Rust, or dict for tests
    budget:        BudgetTracker
    config:        OrchestrationConfig
    token_sink:    asyncio.Queue[str | None] | None = field(default=None, repr=False)
    _slots:        dict[LLMFeature, Any] = field(
        default_factory=dict, init=False, repr=False,
    )

    def get(self, feature: LLMFeature) -> Any:
        """
        Return the LLM client for this feature, constructing it on first access.
        Applies budget-stage degradation and provider circuit-breaker automatically.
        """
        if feature not in self._slots:
            stage = self.budget.stage()
            if stage == BudgetStage.EXHAUSTED:
                from .factory import BudgetExhaustedError  # noqa: PLC0415
                raise BudgetExhaustedError(
                    f"Cannot call {feature} — session budget exhausted"
                )
            client = LLMFactory.create(feature, stage, self.config)
            self._slots[feature] = client
            logger.debug("Lazy-loaded LLM client for feature=%s stage=%s", feature, stage)
        return self._slots[feature]

    @property
    def session_id(self) -> str:
        if isinstance(self.session_state, dict):
            return self.session_state.get("session_id", "unknown")
        return str(getattr(self.session_state, "session_id", "unknown"))

    @property
    def current_phase(self) -> str:
        if isinstance(self.session_state, dict):
            return self.session_state.get("current_phase", "ProblemIntake")
        return str(getattr(self.session_state, "current_phase", "ProblemIntake"))


class SessionLLMContextFactory:
    """
    Process-level singleton. Creates a SessionLLMContext for each turn.
    Does NOT create any LLM clients — those are lazy-loaded on first .get() call.
    """

    def __init__(
        self,
        config: OrchestrationConfig,
        redis: Any | None = None,
    ) -> None:
        self._config = config
        self._redis = redis

    async def for_turn(self, session_state: Any) -> SessionLLMContext:
        """
        Create a fresh context for one BA turn.
        Loads the session's spend from Redis (or starts at 0.0 for tests).
        """
        session_id = (
            session_state.get("session_id", "unknown")
            if isinstance(session_state, dict)
            else str(getattr(session_state, "session_id", "unknown"))
        )
        budget = await BudgetTracker.load(session_id=session_id, redis=self._redis)
        return SessionLLMContext(
            session_state=session_state,
            budget=budget,
            config=self._config,
        )
