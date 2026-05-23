"""GapAnalyzerNode — identifies the highest-priority unmet AC criterion.

Model: claude-haiku-4-5-20251001 (fast tier — gap analysis is latency-sensitive)
Timeout: 3000ms
Output: state["gap_analysis"] — GapResult with the next question for the BA

Fallback (timeout or parse error): reads the first unmet criterion directly from
the session state's ac_unmet list — no LLM required, deterministic result.

When gap_analysis.is_terminal is True, all AC for the current phase are met
and the GuidanceGeneratorNode will offer the phase transition.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..llm.features import LLMFeature
from ..models.entities import AcUpdate, Entity, GapResult
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_TERMINAL_GAP = GapResult(
    criterion_id="TERMINAL",
    description="All acceptance criteria met for this phase.",
    suggested_question="",
    is_terminal=True,
    unmet_count=0,
)

# Phase → ordered list of (criterion_id, description, fallback_question) for deterministic fallback
_PHASE_AC_FALLBACKS: dict[str, list[tuple[str, str, str]]] = {
    "ProblemIntake": [
        ("AC-S1-01", "Problem statement", "Can you describe the business problem in a few sentences?"),
        ("AC-S1-02", "Business domain", "What industry or business domain does this project operate in?"),
        ("AC-S1-03", "Primary goal", "What is the single most important outcome this project needs to achieve?"),
        ("AC-S1-04", "Pain point", "What is the biggest pain point the current process has?"),
        ("AC-S1-05", "Scope boundary", "Are there things explicitly out of scope for this project?"),
    ],
    "StakeholderDiscovery": [
        ("AC-S2-01", "Actors identified", "Who are the main types of users that will interact with this system?"),
        ("AC-S2-02", "Decision-maker", "Who is the single most important stakeholder that will sign off on this project?"),
        ("AC-S2-03", "External systems", "Does this system need to connect with any existing tools or services?"),
        ("AC-S2-04", "Success definition", "How will the client know this project has been successful?"),
        ("AC-S2-05", "Regulatory context", "Are there any regulatory or compliance requirements to be aware of?"),
    ],
    "RequirementElicitation": [
        ("AC-S3-01", "Five functional requirements", "Let's keep going — what else does the system need to do?"),
        ("AC-S3-02", "Non-functional requirement", "Are there any performance or reliability targets?"),
        ("AC-S3-03", "Actor linkage", "Who specifically needs this feature — which user role does it serve?"),
        ("AC-S3-04", "No conflicts", "Are there any conflicting requirements we need to resolve?"),
        ("AC-S3-05", "Acceptance criterion", "For the most critical requirement, how would you test that it works?"),
    ],
    "ConstraintCapture": [
        ("AC-S4-01", "Budget", "Is there a budget range or ceiling for this project?"),
        ("AC-S4-02", "Timeline", "Is there a target delivery date or deadline?"),
        ("AC-S4-03", "Tech constraints", "Are there any technology constraints or mandated platforms?"),
        ("AC-S4-04", "Data residency", "Where does the data need to be stored?"),
        ("AC-S4-05", "Assumptions", "Let me read back the assumptions we've been working from — do they look correct?"),
    ],
}


class GapAnalyzerNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.gap_analyzer

    async def __call__(self, state: PipelineState) -> PipelineState:
        return await self._run_with_timeout(
            self._analyze(state),
            state,
            default={**state, "gap_analysis": _deterministic_fallback(state)},
        )

    async def _analyze(self, state: PipelineState) -> PipelineState:
        client = state["llm_ctx"].get(LLMFeature.RAG_SYNTHESIS)
        tier = self._config.models.function_map.rag_synthesis
        model = self._config.model_id(tier)
        system = _PROMPTS_DIR.joinpath("gap_analyzer.txt").read_text(encoding="utf-8")

        gap_input = _build_gap_input(state)
        response = await client.messages.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": json.dumps(gap_input)}],
            max_tokens=512,
        )

        raw = response.content[0].text.strip() if response.content else ""
        gap = _parse_gap(raw) or _deterministic_fallback(state)

        logger.debug(
            "GapAnalyzer → criterion=%s terminal=%s unmet=%d",
            gap.criterion_id, gap.is_terminal, gap.unmet_count,
        )
        return {**state, "gap_analysis": gap}


def _build_gap_input(state: PipelineState) -> dict:
    ss = state["session_state"]
    phase = state["llm_ctx"].current_phase
    entities: list[Entity] = state.get("extracted_entities") or []

    def get(name: str, default=None):
        if isinstance(ss, dict):
            return ss.get(name, default)
        return getattr(ss, name, default)

    # Project this turn's entities onto the snapshot for a forward-looking view
    actor_count = len(get("actors") or []) + sum(1 for e in entities if e.entity_type == "actor")
    req_count = len(get("requirements") or []) + sum(1 for e in entities if e.entity_type == "requirement")

    snapshot = {
        "problem_statement": get("problem_statement"),
        "domain": get("business_domain"),
        "actors": actor_count,
        "requirements": req_count,
        "constraints": len(get("constraints") or []),
        "assumptions": len(get("assumptions") or []),
        "open_questions": len(get("open_questions") or []),
        "documents_indexed": len(get("documents_indexed") or []),
        "regulatory_context": get("regulatory_context"),
        "success_definition": get("success_definition"),
        "architecture_approach": get("architecture_approach"),
        "deployment_environment": get("deployment_environment"),
    }

    ac_met = list(get("ac_met") or [])
    ac_waived = list(get("ac_waived") or [])
    fallbacks = _PHASE_AC_FALLBACKS.get(phase, [])
    ac_criteria = [
        {
            "criterion_id": cid,
            "description": desc,
            "met": cid in ac_met,
            "waived": cid in ac_waived,
            "priority": i + 1,
        }
        for i, (cid, desc, _) in enumerate(fallbacks)
    ]

    chunks = [
        {
            "chunk_id": str(c.chunk_id),
            "content": c.content[:500],
            "score": c.score,
            "section_title": c.section_title,
            "page_number": c.page_number,
        }
        for c in (state.get("retrieved_chunks") or [])
    ]

    return {
        "current_phase": phase,
        "ac_criteria": ac_criteria,
        "session_snapshot": snapshot,
        "retrieved_chunks": chunks,
    }


def _parse_gap(raw: str) -> GapResult | None:
    try:
        data = json.loads(raw)
        return GapResult(
            criterion_id=data["criterion_id"],
            description=data["description"],
            suggested_question=data.get("suggested_question", ""),
            priority=int(data.get("priority", 0)),
            is_terminal=bool(data.get("is_terminal", False)),
            unmet_count=int(data.get("unmet_count", 0)),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def _deterministic_fallback(state: PipelineState) -> GapResult:
    """Return the first unmet criterion from the fallback table — no LLM needed."""
    phase = state["llm_ctx"].current_phase
    ss = state["session_state"]
    ac_met: list[str] = (
        ss.get("ac_met", []) if isinstance(ss, dict) else list(getattr(ss, "ac_met", []))
    )
    ac_waived: list[str] = (
        ss.get("ac_waived", []) if isinstance(ss, dict) else list(getattr(ss, "ac_waived", []))
    )

    fallbacks = _PHASE_AC_FALLBACKS.get(phase, [])
    unmet = [
        (cid, desc, q)
        for cid, desc, q in fallbacks
        if cid not in ac_met and cid not in ac_waived
    ]

    if not unmet:
        return _TERMINAL_GAP

    cid, desc, question = unmet[0]
    return GapResult(
        criterion_id=cid,
        description=desc,
        suggested_question=question,
        priority=1,
        is_terminal=False,
        unmet_count=len(unmet),
    )
