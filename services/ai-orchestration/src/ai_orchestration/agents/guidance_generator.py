"""GuidanceGeneratorNode — streams the BA-facing response.

Model selection (from LLM_DEGRADATION.md):
  ReviewAndSignOff phase → BRD_GENERATION (Opus, or Sonnet at caution/critical)
  All other phases      → REQUIREMENT_REFINEMENT (Sonnet, or Haiku at critical)

Timeout: 20 000ms (covers long BRD streaming responses)

This is the ONLY streaming node. Tokens are placed on llm_ctx.token_sink
(asyncio.Queue) as they arrive. The executor drains this queue and forwards
tokens upstream to the gRPC servicer.

Failure here is the only unrecoverable pipeline failure — sets pipeline_aborted=True.
"""
from __future__ import annotations

import logging

from ..config import OrchestrationConfig
from ..llm.features import LLMFeature
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)

_SIGN_OFF_PHASE = "ReviewAndSignOff"


class GuidanceGeneratorNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.guidance_generator

    async def __call__(self, state: PipelineState) -> PipelineState:
        try:
            return await self._generate(state)
        except Exception as exc:
            logger.exception("GuidanceGenerator failed unrecoverably")
            # Signal the executor to abort and send an error message to the BA
            sink = state["llm_ctx"].token_sink
            if sink is not None:
                await sink.put(None)  # close the stream
            return {
                **state,
                "guidance_tokens": [],
                "pipeline_aborted": True,
                "node_errors": {
                    **state["node_errors"],
                    "GuidanceGeneratorNode": str(exc),
                },
            }

    async def _generate(self, state: PipelineState) -> PipelineState:
        phase = state["llm_ctx"].current_phase
        feature = (
            LLMFeature.BRD_GENERATION
            if phase == _SIGN_OFF_PHASE
            else LLMFeature.REQUIREMENT_REFINEMENT
        )

        # TODO(sprint1): implement streaming generation
        # client = state["llm_ctx"].get(feature)
        # async with client.stream(system=..., user=...) as stream:
        #     async for token in stream:
        #         tokens.append(token)
        #         if state["llm_ctx"].token_sink is not None:
        #             await state["llm_ctx"].token_sink.put(token)
        #
        # Stub: emit a single placeholder token so the stream doesn't hang
        _ = state["llm_ctx"].get(feature)
        tokens: list[str] = []
        sink = state["llm_ctx"].token_sink
        if sink is not None:
            placeholder = "[GuidanceGenerator not yet implemented]"
            await sink.put(placeholder)
            tokens.append(placeholder)
            await sink.put(None)  # sentinel — close the stream

        logger.debug("GuidanceGenerator → %d tokens streamed", len(tokens))
        return {**state, "guidance_tokens": tokens}
