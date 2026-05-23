"""E2E Suite — REVISIT Round-Trip.

T-E2E-04: Phase 4 → revisit Phase 2 → resume to Phase 4.

Requires: Full Docker Compose stack + OPENROUTER_API_KEY.
Run with: pytest -m e2e
"""
import pytest


@pytest.mark.e2e
@pytest.mark.skip(reason="Requires full Docker Compose stack + API keys. Run with: pytest -m e2e")
async def test_e2e_04_revisit_phase_4_to_2_and_resume_to_4():
    """
    T-E2E-04: Progress to Phase 4, trigger a REVISIT to Phase 2, complete Phase 2
    again, then resume forward to Phase 4.

    Acceptance criteria:
    1. Reach Phase 4 (ConstraintCapture) normally
    2. Send a REVISIT-to-Phase-2 message
    3. current_phase must become StakeholderDiscovery
    4. All Phase 4 entities must still be present in session state
    5. Complete Phase 2 requirements again
    6. Resume forward through Phase 3 to Phase 4

    Requires: Full stack + real LLM calls.
    """
    raise NotImplementedError("E2E test — requires full Docker Compose stack.")
