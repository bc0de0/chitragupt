"""IntentClassifierNode — classifies a BA turn into one of 8 intent codes.

Model: claude-haiku-4-5-20251001 (fast tier)
Timeout: 800ms
Output: state["intent"] — one of the 8 intent codes defined below
Fallback: "Clarification" (least disruptive default on failure)

Intent set (from LLM_UNIVERSE.md):
  ProblemCapture | StakeholderProbe | RequirementCapture | ConstraintStatement
  ArchitectureComment | ReviewFeedback | UploadRequest | Clarification
"""
from __future__ import annotations

import logging

from ..config import OrchestrationConfig
from ..llm.features import LLMFeature
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)

VALID_INTENTS = frozenset({
    "ProblemCapture",
    "StakeholderProbe",
    "RequirementCapture",
    "ConstraintStatement",
    "ArchitectureComment",
    "ReviewFeedback",
    "UploadRequest",
    "Clarification",
})

_DEFAULT_INTENT = "Clarification"


class IntentClassifierNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.intent_classifier

    async def __call__(self, state: PipelineState) -> PipelineState:
        return await self._run_with_timeout(
            self._classify(state),
            state,
            default={**state, "intent": _DEFAULT_INTENT},
        )

    async def _classify(self, state: PipelineState) -> PipelineState:
        # TODO(sprint1): implement Haiku call with structured JSON output
        # client = state["llm_ctx"].get(LLMFeature.INTENT_CLASSIFICATION)
        # response = await client.messages.create(
        #     model=...,
        #     system=CLASSIFICATION_PROMPT,
        #     messages=[{"role": "user", "content": state["user_message"]}],
        #     max_tokens=32,
        # )
        # intent = _parse_intent(response.content[0].text)
        _ = state["llm_ctx"].get(LLMFeature.INTENT_CLASSIFICATION)  # exercises lazy load
        intent = _DEFAULT_INTENT  # placeholder until implemented
        logger.debug("IntentClassifier → %s", intent)
        return {**state, "intent": intent}
