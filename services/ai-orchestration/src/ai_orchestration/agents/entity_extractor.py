"""EntityExtractorNode — extracts structured entities from the BA turn.

Model: claude-haiku-4-5-20251001 (fast tier)
Timeout: 1500ms
Output: state["extracted_entities"] — list[Entity]
        state["ac_updates"] — AC criteria that changed as a result of this extraction

Entity types extracted: actor, requirement, constraint, assumption
Extraction is phase-specific — the prompt is scoped to what matters in the current phase.
"""
from __future__ import annotations

import logging

from ..config import OrchestrationConfig
from ..llm.features import LLMFeature
from ..models.entities import Entity
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)


class EntityExtractorNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.entity_extractor

    async def __call__(self, state: PipelineState) -> PipelineState:
        return await self._run_with_timeout(
            self._extract(state),
            state,
            default={**state, "extracted_entities": [], "ac_updates": []},
        )

    async def _extract(self, state: PipelineState) -> PipelineState:
        # TODO(sprint1): implement phase-specific entity extraction
        # client = state["llm_ctx"].get(LLMFeature.DATA_TRANSFORMATION)
        # prompt = self._build_prompt(state["session_state"], state["user_message"])
        # response = await client.messages.create(...)
        # entities = _parse_entities(response)
        _ = state["llm_ctx"].get(LLMFeature.DATA_TRANSFORMATION)
        entities: list[Entity] = []  # placeholder
        logger.debug("EntityExtractor → %d entities", len(entities))
        return {**state, "extracted_entities": entities, "ac_updates": []}
