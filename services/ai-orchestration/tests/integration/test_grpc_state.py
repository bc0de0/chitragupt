"""Domain 6 — Code Integration: Go → Rust gRPC State Machine stubs.

T-INT-01: CreateSession then GetSessionState returns matching session_id.
T-INT-02: ApplyTurnResult with entity → GetSessionState shows entity.
T-INT-03: ApplyTurnResult with AcUpdate → unmet_ac_count decreases.
T-INT-04: RequestTransition with all ACs met → approved.
T-INT-05: RevisitPhase to prior phase → ok, current_phase updated.
T-BUD-06: total_cost_usd in SessionStateProto accumulates across ApplyTurnResult calls.

Requires: Rust gRPC state machine + Go gateway (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_int_01_create_session_then_get_state_returns_matching_id():
    """T-INT-01: CreateSession → GetSessionState — session_id matches."""
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_int_02_apply_turn_result_with_entity_stored_in_state():
    """T-INT-02: ApplyTurnResult(entity=actor) → GetSessionState shows actor in actors list."""
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_int_03_apply_turn_result_with_ac_update_decreases_unmet_count():
    """T-INT-03: ApplyTurnResult(AcUpdate met=True) → unmet_ac_count decreases by 1."""
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_int_04_request_transition_approved_when_all_ac_met():
    """T-INT-04: RequestTransition with all required ACs met → approved=True."""
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_int_05_revisit_phase_to_prior_updates_current_phase():
    """T-INT-05: RevisitPhase(target=ProblemIntake) → current_phase=ProblemIntake."""
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_bud_06_total_cost_accumulates_across_apply_turn_result_calls():
    """
    T-BUD-06: After N ApplyTurnResult calls each carrying cost_usd=X,
    SessionStateProto.total_cost_usd must equal N*X.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")
