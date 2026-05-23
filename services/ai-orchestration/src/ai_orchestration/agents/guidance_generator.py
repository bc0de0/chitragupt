"""GuidanceGeneratorNode — streams the BA-facing response.

Model selection (from LLM_DEGRADATION.md):
  ReviewAndSignOff phase → BRD_GENERATION (premium: Opus, or Sonnet at caution/critical)
  All other phases      → REQUIREMENT_REFINEMENT (standard: Sonnet, or Haiku at critical)

Timeout: 20 000ms (covers long BRD streaming responses)

This is the ONLY streaming node. Tokens are placed on llm_ctx.token_sink
(asyncio.Queue) as they arrive. The executor drains this queue and forwards
tokens upstream to the gRPC servicer.

One-action rule (enforced in the system prompt):
  Every response ends with exactly ONE question OR exactly ONE transition offer.
  Never both. Never zero.

Failure here is the only unrecoverable pipeline failure — sets pipeline_aborted=True.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..llm.features import LLMFeature
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_SIGN_OFF_PHASE = "ReviewAndSignOff"

_PHASE_NEXT: dict[str, str] = {
    "ProblemIntake": "Stakeholder Discovery",
    "StakeholderDiscovery": "Requirement Elicitation",
    "RequirementElicitation": "Constraint Capture",
    "ConstraintCapture": "Architecture Alignment",
    "ArchitectureAlignment": "Review & Sign-Off",
    "ReviewAndSignOff": "Sign-Off",
}


class GuidanceGeneratorNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.guidance_generator

    async def __call__(self, state: PipelineState) -> PipelineState:
        try:
            return await self._generate(state)
        except Exception as exc:
            logger.exception("GuidanceGenerator failed unrecoverably")
            sink = state["llm_ctx"].token_sink
            if sink is not None:
                await sink.put(None)
            return {
                **state,
                "guidance_tokens": [],
                "pipeline_aborted": True,
                "node_errors": {
                    **state.get("node_errors", {}),
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
        client = state["llm_ctx"].get(feature)

        if feature == LLMFeature.BRD_GENERATION:
            tier = self._config.models.function_map.brd_generation
        else:
            tier = self._config.models.function_map.requirement_refinement
        model = self._config.model_id(tier)

        system = _build_system_prompt(state)
        user_content = _build_user_message(state)

        tokens: list[str] = []
        sink = state["llm_ctx"].token_sink

        async with client.messages.stream(
            model=model,
            system=system,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=1024,
        ) as stream:
            async for text in stream.text_stream:
                tokens.append(text)
                if sink is not None:
                    await sink.put(text)

        if sink is not None:
            await sink.put(None)  # sentinel — close the stream

        logger.debug("GuidanceGenerator → %d tokens streamed (phase=%s)", len(tokens), phase)
        return {**state, "guidance_tokens": tokens}


def _build_system_prompt(state: PipelineState) -> str:
    phase = state["llm_ctx"].current_phase
    gap = state.get("gap_analysis")
    ss = state["session_state"]

    template = _PROMPTS_DIR.joinpath("guidance_generator.txt").read_text(encoding="utf-8")

    gap_description = gap.description if gap else "No gap identified."
    suggested_question = gap.suggested_question if gap else ""
    is_terminal = gap.is_terminal if gap else False

    def get(name: str, default=None):
        if isinstance(ss, dict):
            return ss.get(name, default)
        return getattr(ss, name, default)

    snapshot = json.dumps({
        "problem_statement": get("problem_statement"),
        "domain": get("business_domain"),
        "actor_count": len(get("actors") or []),
        "requirement_count": len(get("requirements") or []),
        "constraint_count": len(get("constraints") or []),
        "open_questions": len(get("open_questions") or []),
    }, indent=2)

    # Fill placeholders
    result = (
        template
        .replace("{{PHASE}}", phase)
        .replace("{{GAP_DESCRIPTION}}", gap_description)
        .replace(
            "{{SUGGESTED_QUESTION}}",
            "" if is_terminal else suggested_question,
        )
        .replace("{{SESSION_SNAPSHOT}}", snapshot)
    )
    return result


def _build_user_message(state: PipelineState) -> str:
    gap = state.get("gap_analysis")
    intent = state.get("intent", "Clarification")
    entities = state.get("extracted_entities") or []
    is_terminal = gap.is_terminal if gap else False

    parts: list[str] = []

    if entities:
        entity_summary = "; ".join(
            f"{e.entity_type}: {e.value[:80]}" for e in entities[:5]
        )
        parts.append(f"[Captured this turn: {entity_summary}]")

    if is_terminal:
        next_phase = _PHASE_NEXT.get(state["llm_ctx"].current_phase, "the next phase")
        parts.append(f"[All AC met — offer transition to {next_phase}]")
    else:
        parts.append(f"[BA message intent: {intent}]")

    parts.append(f"BA message: {state['user_message']}")
    return "\n".join(parts)
