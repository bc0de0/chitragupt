"""Domain 2 — Edge Cases: RevisitHandlerNode tests.

T-EDGE-10 (REVISIT with no recognisable target phase → Clarification) is
covered in test_edge_cases.py. This file adds additional revisit handler tests.
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import make_state

from ai_orchestration.agents.revisit_handler import RevisitHandlerNode
from ai_orchestration.config import OrchestrationConfig


@pytest.fixture
def cfg() -> OrchestrationConfig:
    return OrchestrationConfig()


@pytest.mark.fast
async def test_revisit_handler_problem_keyword_resolves_phase_1(cfg):
    """'problem' keyword → resolves to ProblemIntake phase."""
    node = RevisitHandlerNode(cfg)
    state = make_state(message="Let's revisit the problem we defined earlier.")

    result = await node(state)

    gap = result["gap_analysis"]
    assert gap is not None
    assert gap.criterion_id != "REVISIT-UNKNOWN", (
        "Expected a resolved phase gap, not REVISIT-UNKNOWN"
    )


@pytest.mark.fast
async def test_revisit_handler_result_is_not_terminal(cfg):
    """A REVISIT result must not be a terminal gap — the BA needs to re-confirm."""
    node = RevisitHandlerNode(cfg)
    state = make_state(message="Go back to the stakeholders we discussed.")

    result = await node(state)

    gap = result["gap_analysis"]
    assert gap is not None
    assert gap.is_terminal is False, "REVISIT should never return a terminal gap"


@pytest.mark.fast
async def test_revisit_handler_pipeline_does_not_abort(cfg):
    """REVISIT processing must never set pipeline_aborted."""
    node = RevisitHandlerNode(cfg)
    state = make_state(message="I want to revisit something.")

    result = await node(state)

    assert result["pipeline_aborted"] is False
