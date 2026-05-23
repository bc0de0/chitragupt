"""E2E Suite — Full 4-Phase BA Journey.

T-E2E-01: Full Phase 1→4 journey via conversation alone (no document uploads).

Requires: Full Docker Compose stack + OPENROUTER_API_KEY.
Run with: pytest -m e2e
"""
import pytest


@pytest.mark.e2e
@pytest.mark.skip(reason="Requires full Docker Compose stack + API keys. Run with: pytest -m e2e")
async def test_e2e_01_full_4_phase_journey_via_conversation():
    """
    T-E2E-01: Complete a full BA engagement from Phase 1 (ProblemIntake) through
    Phase 4 (ConstraintCapture) using only conversation turns — no document uploads.

    Acceptance criteria:
    - All Phase 1–4 required ACs are satisfied by conversation turns
    - Phase transitions are approved by the Rust state machine at each boundary
    - Each turn returns exactly one question or one transition offer (one-action rule)
    - Final SSE event is 'complete' with a non-empty guidance_text

    Requires: Full stack + real LLM calls via OPENROUTER_API_KEY.
    """
    raise NotImplementedError("E2E test — requires full Docker Compose stack.")
