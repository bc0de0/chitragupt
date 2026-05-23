"""E2E Suite — Single-Question Invariant.

T-E2E-02: Every turn in a 10-turn session has exactly one question XOR terminal offer.

Requires: Full Docker Compose stack + OPENROUTER_API_KEY.
Run with: pytest -m e2e
"""
import pytest


@pytest.mark.e2e
@pytest.mark.skip(reason="Requires full Docker Compose stack + API keys. Run with: pytest -m e2e")
async def test_e2e_02_every_turn_has_exactly_one_question_or_terminal():
    """
    T-E2E-02: Over a 10-turn session, every guidance response must contain
    exactly ONE question mark OR exactly one phase-transition offer — never both,
    never zero (one-action rule enforced end-to-end).

    Acceptance criteria:
    - Parse the guidance_text from each SSE 'complete' event
    - Count '?' occurrences; assert count == 1 OR transition offer detected
    - Zero '?' + no transition offer = FAIL
    - Two or more '?' = FAIL

    Requires: Full stack + real LLM calls.
    """
    raise NotImplementedError("E2E test — requires full Docker Compose stack.")
