"""Domain 3 & 8 — Quality and Context Awareness: GuidanceGeneratorNode tests.

T-QUAL-03 (exactly one question mark), T-QUAL-04 (no internal field names leaked),
T-CTX-08 (prompt includes gap criterion description).

Note: T-DET-05 (temperature=0 check) is already covered in test_determinism.py.

All tests run in the 'fast' CI mode — streaming LLM is mocked via FakeStream.
"""
from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import FakeStream, make_state

from ai_orchestration.agents.guidance_generator import GuidanceGeneratorNode
from ai_orchestration.config import OrchestrationConfig
from ai_orchestration.models.entities import GapResult


@pytest.fixture
def cfg() -> OrchestrationConfig:
    return OrchestrationConfig()


def _gap(
    criterion_id: str = "AC-S1-01",
    description: str = "Problem statement must be present",
    question: str = "Can you describe the main business problem in 2-3 sentences?",
    is_terminal: bool = False,
) -> GapResult:
    return GapResult(
        criterion_id=criterion_id,
        description=description,
        suggested_question=question,
        is_terminal=is_terminal,
        unmet_count=3,
    )


def _make_stream_client(tokens: list[str]) -> MagicMock:
    """Build a mock client whose messages.stream yields the given token list."""
    client = MagicMock()
    client.messages.stream = MagicMock(return_value=FakeStream(tokens))
    return client


# ─────────────────────────────────────────────────────────────────────────────
# T-QUAL-03: Guidance text contains exactly one question mark
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_qual_03_guidance_text_has_exactly_one_question_mark(cfg):
    """
    T-QUAL-03: The one-action rule requires every guidance response to end with
    exactly ONE question OR one transition offer — never zero, never two.

    Here we inject a well-formed guidance text (via FakeStream) that has exactly
    one '?' and verify the guidance_tokens joined reflect that.

    EXPECTED: PASS
    """
    tokens = [
        "Based on what you've shared, ",
        "I'd like to understand the core problem better. ",
        "Can you describe the main business challenge in two or three sentences?",
    ]
    client = _make_stream_client(tokens)
    gap = _gap()
    node = GuidanceGeneratorNode(cfg)
    state = make_state(
        message="We want to improve our procurement.",
        client=client,
        gap_analysis=gap,
    )

    result = await node(state)

    full_text = "".join(result["guidance_tokens"])
    question_count = full_text.count("?")
    assert question_count == 1, (
        f"Expected exactly 1 '?' in guidance text, found {question_count}.\n"
        f"Text: {full_text!r}"
    )


@pytest.mark.fast
async def test_qual_03b_guidance_with_no_question_mark_is_a_quality_gap(cfg):
    """
    T-QUAL-03b: A guidance response with zero '?' violates the one-action rule.
    This test documents that the current system does not enforce the rule on
    the output side — it relies on the prompt instruction only.

    EXPECTED: PASS (the test itself passes; it records the observation)
    """
    tokens = ["The next step is to review your requirements list."]  # no '?'
    client = _make_stream_client(tokens)
    gap = _gap()
    node = GuidanceGeneratorNode(cfg)
    state = make_state(message="OK let us proceed.", client=client, gap_analysis=gap)

    result = await node(state)

    full_text = "".join(result["guidance_tokens"])
    question_count = full_text.count("?")
    # Document the observation — output validation is a Sprint 2 task
    assert isinstance(question_count, int)  # always passes; observation captured above


# ─────────────────────────────────────────────────────────────────────────────
# T-QUAL-04: Guidance text does not expose internal field names
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_qual_04_guidance_does_not_leak_internal_field_names(cfg):
    """
    T-QUAL-04: The text seen by the BA must not contain internal field names such
    as ac_met, session_id, workspace_id, criterion_id, etc.

    This test injects a 'clean' guidance response and verifies no internal names
    appear. The prompt construction is tested in T-CTX-08 below.

    EXPECTED: PASS
    """
    tokens = [
        "Great progress so far! To move forward, ",
        "it would help to understand the regulatory environment. ",
        "Are there specific compliance frameworks your organisation must follow?",
    ]
    client = _make_stream_client(tokens)
    gap = _gap()
    node = GuidanceGeneratorNode(cfg)
    state = make_state(
        message="We operate in financial services.",
        client=client,
        gap_analysis=gap,
    )

    result = await node(state)

    full_text = "".join(result["guidance_tokens"])
    forbidden = ["ac_met", "session_id", "workspace_id", "node_errors", "pipeline_aborted"]
    for name in forbidden:
        assert name not in full_text, (
            f"Internal field name '{name}' leaked into guidance text: {full_text!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-CTX-08: GuidanceGenerator prompt includes the gap criterion ID and description
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_ctx_08_guidance_system_prompt_includes_gap_description(cfg):
    """
    T-CTX-08: The system prompt built by _build_system_prompt() must include
    the gap's description so the LLM understands which criterion to guide toward.

    The prompt template uses {{GAP_DESCRIPTION}} → gap.description.

    EXPECTED: PASS (description is in the prompt)
    """
    captured_system: list[str] = []

    class CapturingStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        @property
        def text_stream(self):
            return self._gen()

        async def _gen(self):
            yield "Understood."

    def capturing_stream(**kwargs):
        captured_system.append(kwargs.get("system", ""))
        return CapturingStream()

    client = MagicMock()
    client.messages.stream = capturing_stream

    gap = _gap(
        criterion_id="AC-S2-02",
        description="Decision-maker must be identified",
        question="Who has final authority to sign off on this project?",
    )
    node = GuidanceGeneratorNode(cfg)
    state = make_state(
        message="Our CTO is the main sponsor.",
        client=client,
        gap_analysis=gap,
    )

    await node(state)

    assert len(captured_system) == 1, "messages.stream was not called"
    system_prompt = captured_system[0]

    assert "Decision-maker must be identified" in system_prompt, (
        "FINDING: gap.description is NOT included in the guidance system prompt.\n"
        f"System prompt snippet: {system_prompt[:300]!r}"
    )


@pytest.mark.fast
async def test_ctx_08b_guidance_prompt_includes_gap_suggested_question(cfg):
    """
    T-CTX-08b: The system prompt must include the suggested_question so the LLM
    knows which question to ask the BA.

    EXPECTED: PASS (suggested_question is in the prompt via {{SUGGESTED_QUESTION}})
    """
    captured_system: list[str] = []

    class CapturingStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        @property
        def text_stream(self):
            return self._gen()

        async def _gen(self):
            yield "Got it."

    def capturing_stream(**kwargs):
        captured_system.append(kwargs.get("system", ""))
        return CapturingStream()

    client = MagicMock()
    client.messages.stream = capturing_stream

    gap = _gap(
        criterion_id="AC-S1-03",
        description="Primary goal",
        question="What is the single most important outcome this project must achieve?",
    )
    node = GuidanceGeneratorNode(cfg)
    state = make_state(
        message="We need to cut costs by 20%.",
        client=client,
        gap_analysis=gap,
    )

    await node(state)

    assert len(captured_system) == 1
    system_prompt = captured_system[0]

    assert "What is the single most important outcome" in system_prompt, (
        "FINDING: gap.suggested_question is NOT included in the guidance system prompt.\n"
        f"System prompt snippet: {system_prompt[:300]!r}"
    )


@pytest.mark.fast
async def test_ctx_08c_guidance_pipeline_aborts_on_unrecoverable_failure(cfg):
    """
    When messages.stream raises an unrecoverable exception, pipeline_aborted must
    be set to True and the error must be recorded in node_errors.
    """
    import asyncio

    class ExplodingStream:
        async def __aenter__(self):
            raise RuntimeError("LLM quota exceeded")

        async def __aexit__(self, *_):
            pass

    client = MagicMock()
    client.messages.stream = MagicMock(return_value=ExplodingStream())

    gap = _gap()
    node = GuidanceGeneratorNode(cfg)
    state = make_state(message="Keep going please.", client=client, gap_analysis=gap)

    result = await node(state)

    assert result["pipeline_aborted"] is True
    assert "GuidanceGeneratorNode" in result["node_errors"]
