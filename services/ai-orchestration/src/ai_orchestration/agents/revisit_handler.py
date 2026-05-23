"""RevisitHandlerNode — handles BA requests to re-enter a prior phase.

Triggered when IntentClassifierNode returns "REVISIT".

Responsibilities:
  1. Extract the target phase from the BA message.
  2. Update session_state["current_phase"] to the target (for dict-mode sessions;
     Rust mutation happens at the gRPC service layer in Block F).
  3. Build a GapResult for the highest-priority open criterion in the target phase.
  4. Set state["gap_analysis"] so GuidanceGeneratorNode produces a proper re-entry response.

Skips entity extraction and RAG retrieval — those happen on the subsequent turn
after the BA confirms or adds new information in the revisited phase.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..llm.features import LLMFeature
from ..models.entities import GapResult
from ..pipeline.state import PipelineState
from .base import PipelineNode
from .gap_analyzer import _PHASE_AC_FALLBACKS, _TERMINAL_GAP

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Keyword → phase name mapping for target phase extraction
_PHASE_ALIASES: dict[str, str] = {
    "problem":          "ProblemIntake",
    "problem intake":   "ProblemIntake",
    "intent":           "ProblemIntake",
    "stakeholder":      "StakeholderDiscovery",
    "stakeholders":     "StakeholderDiscovery",
    "actor":            "StakeholderDiscovery",
    "actors":           "StakeholderDiscovery",
    "requirement":      "RequirementElicitation",
    "requirements":     "RequirementElicitation",
    "constraint":       "ConstraintCapture",
    "constraints":      "ConstraintCapture",
    "budget":           "ConstraintCapture",
    "timeline":         "ConstraintCapture",
    "architecture":     "ArchitectureAlignment",
    "arch":             "ArchitectureAlignment",
    "review":           "ReviewAndSignOff",
    "sign":             "ReviewAndSignOff",
}

_VALID_REVISIT_PHASES = frozenset(_PHASE_ALIASES.values()) - {"ReviewAndSignOff"}


class RevisitHandlerNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return 2000  # fast — no LLM call, just state manipulation

    async def __call__(self, state: PipelineState) -> PipelineState:
        return await self._run_with_timeout(
            self._handle(state),
            state,
            default={**state, "gap_analysis": _TERMINAL_GAP},
        )

    async def _handle(self, state: PipelineState) -> PipelineState:
        message = state["user_message"].lower()
        target_phase = _extract_target_phase(message)

        if target_phase is None:
            # Cannot determine target — treat as Clarification
            logger.warning("RevisitHandler: cannot determine target phase from message")
            gap = GapResult(
                criterion_id="REVISIT-UNKNOWN",
                description="Target phase for revisit is unclear.",
                suggested_question=(
                    "Which part of our conversation would you like to go back to — "
                    "the problem statement, stakeholders, requirements, or constraints?"
                ),
                is_terminal=False,
                unmet_count=0,
            )
            return {**state, "gap_analysis": gap}

        # Mutate session_state if it's a dict (test/stub mode)
        ss = state["session_state"]
        if isinstance(ss, dict):
            ss = {**ss, "current_phase": target_phase, "revisit_target": target_phase}
            state = {**state, "session_state": ss}

        # Build the re-entry gap for the target phase
        ac_met: list[str] = (
            ss.get("ac_met", []) if isinstance(ss, dict) else list(getattr(ss, "ac_met", []))
        )
        ac_waived: list[str] = (
            ss.get("ac_waived", []) if isinstance(ss, dict) else list(getattr(ss, "ac_waived", []))
        )
        fallbacks = _PHASE_AC_FALLBACKS.get(target_phase, [])
        unmet = [
            (cid, desc, q)
            for cid, desc, q in fallbacks
            if cid not in ac_met and cid not in ac_waived
        ]

        if unmet:
            cid, desc, question = unmet[0]
            gap = GapResult(
                criterion_id=cid,
                description=f"Revisiting {target_phase} — {desc}",
                suggested_question=question,
                is_terminal=False,
                unmet_count=len(unmet),
            )
        else:
            # All AC already met in target phase — still surface it as a revisit
            gap = GapResult(
                criterion_id="REVISIT-CONFIRMED",
                description=f"All criteria already met in {target_phase}.",
                suggested_question=(
                    f"We are back at {target_phase.replace('And', ' and ')}. "
                    "Everything here is preserved. Is there something specific you would like to update?"
                ),
                is_terminal=False,
                unmet_count=0,
            )

        logger.debug(
            "RevisitHandler → target=%s gap=%s", target_phase, gap.criterion_id
        )
        # Signal to the guidance generator that this is a revisit response
        return {
            **state,
            "intent": f"REVISIT:{target_phase}",
            "gap_analysis": gap,
            "extracted_entities": [],
            "ac_updates": [],
        }


def _extract_target_phase(message: str) -> str | None:
    for alias, phase in _PHASE_ALIASES.items():
        if alias in message:
            if phase in _VALID_REVISIT_PHASES:
                return phase
    return None
