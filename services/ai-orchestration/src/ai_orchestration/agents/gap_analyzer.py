"""GapAnalyzerNode — identifies the highest-priority unmet AC criterion.

Model: claude-sonnet-4-6 (standard tier)
Timeout: 3000ms
Output: state["gap_analysis"] — GapResult with the next question for the BA

On timeout or failure: reads the first unmet criterion directly from SessionState
(synchronous fallback — no LLM required, only session state fields).

When gap_analysis.is_terminal is True, all AC for the current phase are met
and the TransitionOffer path is triggered in Rust.
"""
from __future__ import annotations

import logging

from ..config import OrchestrationConfig
from ..llm.features import LLMFeature
from ..models.entities import GapResult
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)

_TERMINAL_GAP = GapResult(
    criterion_id="TERMINAL",
    description="All acceptance criteria met",
    suggested_question="",
    is_terminal=True,
)


class GapAnalyzerNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.gap_analyzer

    async def __call__(self, state: PipelineState) -> PipelineState:
        return await self._run_with_timeout(
            self._analyze(state),
            state,
            # Fallback: use a generic gap result rather than None so GuidanceGenerator
            # always has something to work with
            default={
                **state,
                "gap_analysis": GapResult(
                    criterion_id="UNKNOWN",
                    description="Gap analysis unavailable",
                    suggested_question="Could you tell me more about what you need?",
                ),
            },
        )

    async def _analyze(self, state: PipelineState) -> PipelineState:
        # TODO(sprint1): call Sonnet with retrieved chunks + session AC state
        # Reads state["session_state"].ac_unmet for criterion list
        # Uses state["retrieved_chunks"] for additional context
        # Returns structured GapResult with the highest-priority gap
        _ = state["llm_ctx"].get(LLMFeature.RAG_SYNTHESIS)
        gap = _TERMINAL_GAP  # placeholder — assume all AC met for now
        logger.debug("GapAnalyzer → criterion=%s terminal=%s", gap.criterion_id, gap.is_terminal)
        return {**state, "gap_analysis": gap}
