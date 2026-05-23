"""Domain 1 & 2 — IntentClassifier component tests.

Test IDs T-DET-01, T-DET-02, T-EDGE-01, T-EDGE-03, T-EDGE-04 are implemented
in test_determinism.py and test_edge_cases.py respectively.

This file adds supplementary intent-classifier-specific tests not captured
in the domain-grouped files.
"""
from __future__ import annotations

import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import make_state, mock_create_client

from ai_orchestration.agents.intent_classifier import (
    IntentClassifierNode,
    VALID_INTENTS,
    _parse_intent,
    _maybe_revisit,
)
from ai_orchestration.config import OrchestrationConfig


@pytest.fixture
def cfg() -> OrchestrationConfig:
    return OrchestrationConfig()


@pytest.mark.fast
async def test_intent_all_valid_codes_accepted(cfg):
    """Every code in VALID_INTENTS must survive the round-trip through _parse_intent."""
    for intent_code in VALID_INTENTS:
        raw = f'{{"intent": "{intent_code}"}}'
        assert _parse_intent(raw) == intent_code, (
            f"Valid intent {intent_code!r} was not accepted by _parse_intent"
        )


@pytest.mark.fast
async def test_intent_unknown_code_maps_to_clarification(cfg):
    """An unknown intent code must fall back to Clarification."""
    assert _parse_intent('{"intent": "DoSomethingWeird"}') == "Clarification"


@pytest.mark.fast
async def test_intent_revisit_keyword_upgrades_clarification(cfg):
    """'revisit' keyword in message upgrades Clarification → REVISIT."""
    result = _maybe_revisit("Clarification", "can we revisit the problem statement?")
    assert result == "REVISIT"


@pytest.mark.fast
async def test_intent_revisit_upgrade_only_on_clarification(cfg):
    """'revisit' keyword must NOT upgrade a non-Clarification intent."""
    result = _maybe_revisit("ProblemCapture", "can we revisit the problem statement?")
    assert result == "ProblemCapture"


@pytest.mark.fast
async def test_intent_classifier_records_error_in_node_errors_on_exception(cfg):
    """Any exception in the LLM call must be caught and recorded in node_errors."""
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=RuntimeError("Network down"))
    node = IntentClassifierNode(cfg)
    state = make_state(message="What are the main goals?", client=client)

    result = await node(state)

    assert result["intent"] == "Clarification"
    assert "IntentClassifierNode" in result["node_errors"]
    assert result["pipeline_aborted"] is False
