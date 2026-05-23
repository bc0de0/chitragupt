"""Domain 1 — LLM Determinism tests.

T-DET-01 through T-DET-06.

Tests in this file verify that:
  (a) the system always sends the correct LLM call parameters (temperature=0),
  (b) identical inputs always produce identical structured outputs regardless of
      when the test runs (parsing and prompt construction are deterministic).

No live LLM calls are made. All tests run in the 'fast' CI mode.

EXPECTED FINDINGS:
  T-DET-01: FAIL — IntentClassifierNode._classify() does not pass temperature=0
  T-DET-05: FAIL — GuidanceGeneratorNode._generate() does not pass temperature=0
  All other tests in this file: PASS
"""
from __future__ import annotations

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import (
    FakeStream,
    make_state,
    mock_create_client,
    mock_stream_client,
    text_response,
)

from ai_orchestration.agents.gap_analyzer import _deterministic_fallback
from ai_orchestration.agents.intent_classifier import (
    IntentClassifierNode,
    VALID_INTENTS,
    _parse_intent,
)
from ai_orchestration.agents.entity_extractor import EntityExtractorNode
from ai_orchestration.agents.guidance_generator import GuidanceGeneratorNode
from ai_orchestration.config import OrchestrationConfig


# ── Shared config ─────────────────────────────────────────────────────────────

@pytest.fixture
def cfg() -> OrchestrationConfig:
    return OrchestrationConfig()


# ─────────────────────────────────────────────────────────────────────────────
# T-DET-01: IntentClassifier sends temperature=0 in every request
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_det_01_intent_classifier_sends_temperature_zero(cfg):
    """
    T-DET-01: IntentClassifierNode must pass temperature=0 to every messages.create call.

    EXPECTED: FAIL
    FINDING:  IntentClassifierNode._classify() does not include temperature in the
              messages.create() kwargs. Non-deterministic LLM output is possible.
    FIX:      Add `temperature=0` to the client.messages.create() call in
              services/ai-orchestration/src/ai_orchestration/agents/intent_classifier.py:82
    """
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=text_response('{"intent": "ProblemCapture"}')
    )

    node = IntentClassifierNode(cfg)
    state = make_state(message="We need a new billing platform.", client=mock_client)

    await node(state)

    assert mock_client.messages.create.called, "LLM client was never called"
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "temperature" in call_kwargs, (
        "FINDING: 'temperature' not in messages.create() kwargs — "
        "LLM calls are non-deterministic. Add temperature=0 to intent_classifier.py."
    )
    assert call_kwargs["temperature"] == 0, (
        f"FINDING: temperature={call_kwargs['temperature']!r} but expected 0."
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-DET-02: Same utterance → same intent code across 3 replayed responses
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_det_02_same_mocked_response_produces_same_intent_three_runs(cfg):
    """
    T-DET-02: The intent parsing layer is deterministic — replaying the same LLM
    response three times must produce the same intent code each time.

    EXPECTED: PASS
    """
    fixed_response = '{"intent": "RequirementCapture"}'

    node = IntentClassifierNode(cfg)
    intents: list[str] = []

    for _ in range(3):
        client = mock_create_client(fixed_response)
        state = make_state(message="We need a login page.", client=client)
        result = await node(state)
        intents.append(result["intent"])

    assert len(set(intents)) == 1, (
        f"Intent was not deterministic across 3 runs: {intents}"
    )
    assert intents[0] == "RequirementCapture"
    assert intents[0] in VALID_INTENTS


# ─────────────────────────────────────────────────────────────────────────────
# T-DET-03: EntityExtractor prompt is byte-for-byte identical for identical input
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_det_03_entity_extractor_prompt_identical_for_same_state(cfg):
    """
    T-DET-03: EntityExtractorNode must construct the same system prompt for
    identical (phase, session_state) inputs across two separate calls.

    EXPECTED: PASS
    """
    captured_systems: list[str] = []

    async def capture_create(*args, **kwargs):
        captured_systems.append(kwargs.get("system", ""))
        return text_response('[{"entity_type":"actor","value":"IT Admin","confidence":0.9}]')

    for _ in range(2):
        client = MagicMock()
        client.messages.create = capture_create
        node = EntityExtractorNode(cfg)
        state = make_state(
            message="The system admin will manage user accounts.",
            phase="StakeholderDiscovery",
            client=client,
        )
        await node(state)

    assert len(captured_systems) == 2
    assert captured_systems[0] == captured_systems[1], (
        "Entity extractor system prompt changed between identical calls. "
        "Prompt construction is not deterministic."
    )
    assert "StakeholderDiscovery" in captured_systems[0], (
        "Phase was not injected into entity extractor prompt."
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-DET-04: GapAnalyzer fallback selects the same criterion for same AC state
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_det_04_gap_analyzer_deterministic_fallback_same_ac_state(cfg):
    """
    T-DET-04: _deterministic_fallback() is a pure function. Calling it three
    times with identical state must return the same criterion_id each time.

    EXPECTED: PASS
    """
    state = make_state(phase="ProblemIntake")

    results = [_deterministic_fallback(state) for _ in range(3)]

    criterion_ids = [r.criterion_id for r in results]
    assert len(set(criterion_ids)) == 1, (
        f"Deterministic fallback returned different criterion IDs across 3 calls: {criterion_ids}"
    )
    assert results[0].criterion_id == "AC-S1-01"
    assert results[0].is_terminal is False
    assert results[0].suggested_question != ""


@pytest.mark.fast
async def test_det_04b_gap_analyzer_fallback_stable_when_first_ac_is_met(cfg):
    """
    T-DET-04b: When AC-S1-01 is met, the fallback must consistently return AC-S1-02.
    """
    session = {
        "session_id": "s1",
        "workspace_id": "w1",
        "current_phase": "ProblemIntake",
        "ac_met": ["AC-S1-01"],
        "ac_waived": [],
        "actors": [], "requirements": [], "constraints": [], "assumptions": [],
        "open_questions": [], "documents_indexed": [],
        "problem_statement": "We need a better system",
        "business_domain": None, "success_definition": None,
        "regulatory_context": None, "architecture_approach": None,
        "deployment_environment": None,
    }
    state = make_state(phase="ProblemIntake", session_state=session)

    results = [_deterministic_fallback(state) for _ in range(3)]
    ids = [r.criterion_id for r in results]

    assert len(set(ids)) == 1
    assert ids[0] == "AC-S1-02"


# ─────────────────────────────────────────────────────────────────────────────
# T-DET-05: GuidanceGenerator sends temperature=0 in stream call
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_det_05_guidance_generator_sends_temperature_zero(cfg):
    """
    T-DET-05: GuidanceGeneratorNode must pass temperature=0 to messages.stream().

    EXPECTED: FAIL
    FINDING:  GuidanceGeneratorNode._generate() does not include temperature in the
              messages.stream() kwargs. Streaming output is non-deterministic.
    FIX:      Add `temperature=0` to the client.messages.stream() call in
              services/ai-orchestration/src/ai_orchestration/agents/guidance_generator.py:92
    """
    from ai_orchestration.models.entities import GapResult

    stream_kwargs_captured: list[dict] = []

    class CapturingStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        @property
        def text_stream(self):
            return self._gen()

        async def _gen(self):
            yield "Here is my guidance."

    def capturing_stream_factory(*args, **kwargs):
        stream_kwargs_captured.append(kwargs)
        return CapturingStream()

    mock_client = MagicMock()
    mock_client.messages.stream = capturing_stream_factory

    gap = GapResult(
        criterion_id="AC-S1-01",
        description="Problem statement",
        suggested_question="Can you describe the business problem?",
        is_terminal=False,
        unmet_count=4,
    )
    node = GuidanceGeneratorNode(cfg)
    state = make_state(
        message="We want to improve our procurement process.",
        client=mock_client,
        gap_analysis=gap,
    )

    await node(state)

    assert len(stream_kwargs_captured) == 1, "messages.stream was never called"
    call_kw = stream_kwargs_captured[0]
    assert "temperature" in call_kw, (
        "FINDING: 'temperature' not in messages.stream() kwargs — "
        "streaming output is non-deterministic. Add temperature=0 to guidance_generator.py."
    )
    assert call_kw["temperature"] == 0, (
        f"FINDING: temperature={call_kw['temperature']!r} but expected 0."
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-DET-06: Full two-node pipeline produces identical output on two identical runs
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_det_06_two_node_pipeline_produces_identical_output_twice(cfg):
    """
    T-DET-06: Running IntentClassifier then EntityExtractor with identical mocked
    responses twice must produce structurally identical state outputs.

    EXPECTED: PASS
    """
    intent_json = '{"intent": "StakeholderProbe"}'
    entity_json = '[{"entity_type":"actor","value":"CFO","confidence":0.95,"source":"conversation"}]'

    async def run_pipeline():
        # IntentClassifier
        intent_client = mock_create_client(intent_json)
        s1 = make_state(message="Who is the decision maker?", client=intent_client)
        intent_node = IntentClassifierNode(cfg)
        s2 = await intent_node(s1)

        # EntityExtractor — reuse same state but swap client
        entity_client = mock_create_client(entity_json)
        s2 = {**s2, "llm_ctx": make_state(client=entity_client)["llm_ctx"]}
        entity_node = EntityExtractorNode(cfg)
        s3 = await entity_node(s2)
        return s3

    run_a = await run_pipeline()
    run_b = await run_pipeline()

    assert run_a["intent"] == run_b["intent"], (
        f"Intent differed between runs: {run_a['intent']!r} vs {run_b['intent']!r}"
    )
    assert len(run_a["extracted_entities"]) == len(run_b["extracted_entities"]), (
        "Entity count differed between runs"
    )
    if run_a["extracted_entities"] and run_b["extracted_entities"]:
        assert run_a["extracted_entities"][0].value == run_b["extracted_entities"][0].value
        assert run_a["extracted_entities"][0].entity_type == run_b["extracted_entities"][0].entity_type
    assert run_a["node_errors"] == run_b["node_errors"]
    assert run_a["pipeline_aborted"] == run_b["pipeline_aborted"]


# ─────────────────────────────────────────────────────────────────────────────
# Supplementary: pure-function determinism checks (no node instantiation needed)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_det_parse_intent_is_pure():
    """_parse_intent is a pure function — same input, same output, always."""
    from ai_orchestration.agents.intent_classifier import _parse_intent

    inputs_and_expected = [
        ('{"intent": "ProblemCapture"}', "ProblemCapture"),
        ('{"intent": "REVISIT"}', "REVISIT"),
        ("not json", "Clarification"),
        ('{"intent": "UNKNOWN_CODE"}', "Clarification"),
        ("", "Clarification"),
        ("{}", "Clarification"),
    ]
    for raw, expected in inputs_and_expected:
        for _ in range(3):
            result = _parse_intent(raw)
            assert result == expected, (
                f"_parse_intent({raw!r}) returned {result!r} but expected {expected!r}"
            )


@pytest.mark.fast
def test_det_maybe_revisit_is_pure():
    """_maybe_revisit is a pure function."""
    from ai_orchestration.agents.intent_classifier import _maybe_revisit

    cases = [
        ("Clarification", "I want to go back to requirements", "REVISIT"),
        ("Clarification", "Can we revisit the actors?", "REVISIT"),
        ("ProblemCapture", "Let's revisit phase 1", "ProblemCapture"),  # only fires on Clarification
        ("Clarification", "What about the timeline?", "Clarification"),  # no keyword
    ]
    for intent, msg, expected in cases:
        for _ in range(3):
            result = _maybe_revisit(intent, msg)
            assert result == expected, (
                f"_maybe_revisit({intent!r}, {msg!r}) → {result!r}, expected {expected!r}"
            )
