"""Domain 2 & 4 & 8 — REVISIT Behaviour: Integration stubs.

T-EDGE-11: REVISIT to current phase → no-op.
T-STATE-10: REVISIT Phase 4→2: phase changes, Phase 4 entities preserved.
T-STATE-11: REVISIT to SignedOff rejected.
T-CTX-05: REVISIT re-entry uses updated AC state (not stale pre-revisit cache).

Requires: Rust gRPC state machine (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_edge_11_revisit_to_current_phase_is_noop():
    """
    T-EDGE-11: RevisitPhase(target=current_phase) must leave current_phase unchanged.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_10_revisit_phase_4_to_2_preserves_entities():
    """
    T-STATE-10: After revisiting Phase 2 from Phase 4, all entities captured in
    Phase 4 must still be present in the session state.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_11_revisit_to_signed_off_is_rejected():
    """
    T-STATE-11: Attempting to revisit the SignedOff phase must be rejected with
    an error (signed-off state is immutable).
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_ctx_05_revisit_reentry_uses_fresh_ac_state():
    """
    T-CTX-05: After a REVISIT, the gap analysis must use the current (updated) AC
    state from the Rust state machine, not a stale cache from before the revisit.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")
