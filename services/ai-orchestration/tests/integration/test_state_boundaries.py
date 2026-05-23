"""Domain 4 — State Boundary Conditions: Integration stubs.

T-STATE-05: Phase 1 → Phase 2 transition approved when all required ACs met.
T-STATE-06: Transition rejected when one required AC short.
T-STATE-12: Forward transition from SignedOff rejected.
T-STATE-13: Double transition returns current_phase unchanged.

Requires: Running Rust gRPC state machine (Docker Compose test profile).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_05_phase_1_to_2_transition_approved_when_all_ac_met():
    """
    T-STATE-05: When all Phase 1 required ACs are met, RequestTransition to Phase 2
    must return approved=True and set current_phase='StakeholderDiscovery'.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_06_transition_rejected_when_one_required_ac_short():
    """
    T-STATE-06: When one required AC is unmet in Phase 1, RequestTransition must
    return approved=False and leave current_phase='ProblemIntake'.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_12_forward_transition_from_signed_off_rejected():
    """
    T-STATE-12: RequestTransition from SignedOff phase must be rejected — there is
    no forward phase after SignedOff.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_13_double_transition_same_target_is_idempotent():
    """
    T-STATE-13: Sending RequestTransition to the same target phase twice must
    return the current_phase unchanged on the second call (idempotent).
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")
