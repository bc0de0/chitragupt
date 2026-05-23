"""Domain 3 — Quality: GapAnalyzerNode tests.

T-QUAL-05 (suggested_question is non-empty and ≥ 10 chars for unmet ACs).

Note: T-DET-04 (deterministic fallback) is already covered in test_determinism.py.

All tests run in the 'fast' CI mode.
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import make_state

from ai_orchestration.agents.gap_analyzer import (
    GapAnalyzerNode,
    _deterministic_fallback,
    _PHASE_AC_FALLBACKS,
)
from ai_orchestration.config import OrchestrationConfig
from ai_orchestration.models.entities import GapResult


@pytest.fixture
def cfg() -> OrchestrationConfig:
    return OrchestrationConfig()


# ─────────────────────────────────────────────────────────────────────────────
# T-QUAL-05: Gap suggested_question is non-empty and ≥ 10 chars for any unmet AC
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_qual_05_all_fallback_questions_are_non_empty_and_min_10_chars():
    """
    T-QUAL-05: Every suggested_question in every fallback entry must be a
    non-empty string with ≥ 10 characters so the BA always receives a useful question.

    This test iterates over ALL entries in _PHASE_AC_FALLBACKS.

    EXPECTED: PASS
    """
    for phase, fallbacks in _PHASE_AC_FALLBACKS.items():
        for criterion_id, description, question in fallbacks:
            assert question, (
                f"Empty suggested_question for {phase}/{criterion_id}"
            )
            assert len(question) >= 10, (
                f"suggested_question too short (<10 chars) for {phase}/{criterion_id}: "
                f"{question!r}"
            )


@pytest.mark.fast
def test_qual_05b_deterministic_fallback_returns_valid_question_for_each_phase():
    """
    T-QUAL-05b: _deterministic_fallback() must return a GapResult with a
    non-empty suggested_question ≥ 10 chars for every known phase.

    EXPECTED: PASS
    """
    for phase in _PHASE_AC_FALLBACKS:
        state = make_state(phase=phase)
        gap = _deterministic_fallback(state)

        assert not gap.is_terminal, (
            f"Phase {phase} should have unmet ACs but is_terminal=True"
        )
        assert gap.suggested_question, (
            f"suggested_question is empty for phase {phase}"
        )
        assert len(gap.suggested_question) >= 10, (
            f"suggested_question too short for phase {phase}: {gap.suggested_question!r}"
        )


@pytest.mark.fast
def test_qual_05c_terminal_gap_when_all_ac_met():
    """
    When all ACs for a phase are met, the gap is terminal and the suggested_question
    should be empty (the LLM will offer a phase transition instead).

    EXPECTED: PASS
    """
    phase = "ProblemIntake"
    all_criteria = [cid for cid, _, _ in _PHASE_AC_FALLBACKS[phase]]

    # Build a session where all ACs are met
    session = {
        "session_id": "s",
        "workspace_id": "w",
        "current_phase": phase,
        "ac_met": all_criteria,
        "ac_waived": [],
        "actors": [], "requirements": [], "constraints": [], "assumptions": [],
        "open_questions": [], "documents_indexed": [],
        "problem_statement": "We need a better system",
        "business_domain": None, "success_definition": None,
        "regulatory_context": None, "architecture_approach": None,
        "deployment_environment": None,
    }
    state = make_state(phase=phase, session_state=session)
    gap = _deterministic_fallback(state)

    assert gap.is_terminal is True
    assert gap.criterion_id == "TERMINAL"
    assert gap.suggested_question == ""


@pytest.mark.fast
def test_qual_05d_waived_ac_does_not_block_progression():
    """
    A waived AC must not appear in the fallback gap list — it is treated as met
    for progression purposes.

    EXPECTED: PASS
    """
    phase = "ProblemIntake"
    # Waive the first 4 ACs, leave only AC-S1-05 unmet
    waived = ["AC-S1-01", "AC-S1-02", "AC-S1-03", "AC-S1-04"]
    session = {
        "session_id": "s",
        "workspace_id": "w",
        "current_phase": phase,
        "ac_met": [],
        "ac_waived": waived,
        "actors": [], "requirements": [], "constraints": [], "assumptions": [],
        "open_questions": [], "documents_indexed": [],
        "problem_statement": None, "business_domain": None,
        "success_definition": None, "regulatory_context": None,
        "architecture_approach": None, "deployment_environment": None,
    }
    state = make_state(phase=phase, session_state=session)
    gap = _deterministic_fallback(state)

    assert gap.criterion_id == "AC-S1-05", (
        f"Expected AC-S1-05 (last unmet), got {gap.criterion_id}"
    )
    assert not gap.is_terminal


@pytest.mark.fast
def test_qual_05e_unknown_phase_returns_terminal_gap():
    """
    An unrecognised phase name has no fallback entries, so the fallback must
    return the TERMINAL gap (all-AC-met signal).

    EXPECTED: PASS
    """
    state = make_state(phase="UnknownPhaseXYZ")
    gap = _deterministic_fallback(state)

    assert gap.is_terminal is True
    assert gap.criterion_id == "TERMINAL"


@pytest.mark.fast
def test_qual_05f_gap_unmet_count_reflects_remaining_criteria():
    """
    GapResult.unmet_count must equal the number of ACs that are neither met nor waived.

    EXPECTED: PASS
    """
    phase = "ProblemIntake"
    session = {
        "session_id": "s",
        "workspace_id": "w",
        "current_phase": phase,
        "ac_met": ["AC-S1-01"],
        "ac_waived": ["AC-S1-02"],
        "actors": [], "requirements": [], "constraints": [], "assumptions": [],
        "open_questions": [], "documents_indexed": [],
        "problem_statement": None, "business_domain": None,
        "success_definition": None, "regulatory_context": None,
        "architecture_approach": None, "deployment_environment": None,
    }
    state = make_state(phase=phase, session_state=session)
    gap = _deterministic_fallback(state)

    # ProblemIntake has 5 ACs. 1 met + 1 waived → 3 remaining unmet.
    assert gap.unmet_count == 3, (
        f"Expected 3 unmet AC, got {gap.unmet_count}"
    )
