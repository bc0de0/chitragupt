"""Domain 2 — Edge Cases: Pipeline executor tests.

T-EDGE-02 (message truncation before LLM) is covered in test_edge_cases.py
(test_edge_02b_oversized_message_is_truncated_before_llm_call).

This file documents that coverage and adds executor-level safety tests.
"""
from __future__ import annotations

import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import make_state, mock_create_client

from ai_orchestration.agents.intent_classifier import IntentClassifierNode, VALID_INTENTS
from ai_orchestration.config import OrchestrationConfig


@pytest.fixture
def cfg() -> OrchestrationConfig:
    return OrchestrationConfig()


@pytest.mark.fast
async def test_executor_pipeline_aborted_flag_starts_false(cfg):
    """A freshly-built PipelineState has pipeline_aborted=False."""
    state = make_state()
    assert state["pipeline_aborted"] is False


@pytest.mark.fast
async def test_executor_oversized_message_does_not_crash_pipeline(cfg):
    """
    T-EDGE-02 (fast mode): A 101K-character message must not crash the pipeline.
    Truncation enforcement is tracked separately in test_edge_cases.py.
    """
    big = "X" * 101_000
    client = mock_create_client('{"intent": "ProblemCapture"}')
    node = IntentClassifierNode(cfg)
    state = make_state(message=big, client=client)

    result = await node(state)

    assert result is not None
    assert result["intent"] in VALID_INTENTS
    assert result["pipeline_aborted"] is False


@pytest.mark.fast
async def test_executor_node_errors_dict_initialized_empty(cfg):
    """node_errors must start as an empty dict so nodes can safely merge into it."""
    state = make_state()
    assert state["node_errors"] == {}
