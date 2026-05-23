"""Domain 1 — LLM Determinism: Integration stub.

T-DET-06: Full pipeline run twice with mocked LLM — TurnResult fields identical.

Requires: Docker Compose test profile (all services running).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Docker Compose test profile. Run with: pytest -m integration")
async def test_det_06_full_pipeline_twice_produces_identical_turn_result():
    """
    T-DET-06: Run the full 5-node pipeline twice with identical mocked LLM responses.
    Both runs must produce structurally identical TurnResult payloads.

    Requires: Running Python AI orchestration service + gRPC servicer.
    """
    raise NotImplementedError("Integration test — requires Docker Compose.")
