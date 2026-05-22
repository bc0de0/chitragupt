"""PipelineNode — abstract base class for all LangGraph nodes.

Contract:
  - Every node is a callable class with one async __call__ method.
  - Nodes MUST NOT raise. All exceptions are caught and written to
    state["node_errors"][self.__class__.__name__].
  - Nodes return the full updated PipelineState (dict spread pattern).
  - Nodes receive config at construction time, not at call time.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from ..config import OrchestrationConfig
from ..pipeline.state import PipelineState

logger = logging.getLogger(__name__)


class PipelineNode(ABC):
    """Base class for all pipeline nodes."""

    def __init__(self, config: OrchestrationConfig) -> None:
        self._config = config

    @abstractmethod
    async def __call__(self, state: PipelineState) -> PipelineState:
        """
        Execute this node.
        Must not raise — catch exceptions and write to state["node_errors"].
        """
        ...

    @property
    def timeout_ms(self) -> int:
        """Per-node timeout from config. Override in subclasses if needed."""
        return 5000

    async def _run_with_timeout(
        self,
        coro: "asyncio.Coroutine[object, object, PipelineState]",
        state: PipelineState,
        default: PipelineState,
    ) -> PipelineState:
        """
        Run coro with the node's configured timeout.
        Returns `default` state on timeout, writing to node_errors.
        """
        try:
            return await asyncio.wait_for(coro, timeout=self.timeout_ms / 1000)
        except asyncio.TimeoutError:
            logger.warning("%s timed out after %dms", self.__class__.__name__, self.timeout_ms)
            return {
                **default,
                "node_errors": {
                    **state["node_errors"],
                    self.__class__.__name__: f"timeout after {self.timeout_ms}ms",
                },
            }
        except Exception as exc:
            logger.exception("%s raised unexpectedly", self.__class__.__name__)
            return {
                **default,
                "node_errors": {
                    **state["node_errors"],
                    self.__class__.__name__: str(exc),
                },
            }
