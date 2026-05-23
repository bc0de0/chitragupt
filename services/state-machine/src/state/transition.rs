use chrono::Utc;
use tracing::{info, warn};

use crate::error::{Result, StateError};
use crate::gates::manager::GateManager;
use crate::state::phase::SessionPhase;
use crate::state::session::{RevisitRecord, SessionState};

pub struct TransitionEngine;

impl TransitionEngine {
    /// Attempt to advance the session to `target`. Returns Ok(()) on success.
    /// Callers must apply `target` to `state.current_phase` after this returns Ok.
    pub fn attempt(
        state: &SessionState,
        target: SessionPhase,
        gate_manager: &GateManager,
    ) -> Result<()> {
        if state.current_phase.is_terminal() {
            return Err(StateError::SessionTerminated);
        }

        let allowed = state.current_phase.valid_transitions();
        if !allowed.contains(&target) {
            return Err(StateError::InvalidTransition {
                from: state.current_phase,
                to: target,
            });
        }

        let open_hard_gates = gate_manager.open_hard_gates(state);
        if !open_hard_gates.is_empty() {
            warn!(
                session_id = %state.session_id,
                gate_count = open_hard_gates.len(),
                "transition blocked by hard gates"
            );
            return Err(StateError::HardGateBlocking {
                gate_count: open_hard_gates.len(),
            });
        }

        let ac = state.current_phase.evaluate_ac(state);
        if !ac.transition_ready {
            warn!(
                session_id = %state.session_id,
                unmet = ac.unmet_count(),
                "transition blocked by unmet AC"
            );
            return Err(StateError::AcNotMet {
                unmet_count: ac.unmet_count(),
            });
        }

        info!(
            session_id = %state.session_id,
            from = %state.current_phase,
            to = %target,
            "phase transition approved"
        );

        Ok(())
    }

    /// Re-enter a prior phase without clearing any captured data.
    ///
    /// Rules:
    /// - SignedOff cannot be revisited (terminal).
    /// - The target must differ from the current phase.
    /// - All Vec fields are preserved — nothing is cleared.
    /// - The revisit is recorded in `revisit_history`.
    pub fn revisit(state: &mut SessionState, target: SessionPhase) -> Result<()> {
        if target == SessionPhase::SignedOff {
            return Err(StateError::InvalidTransition {
                from: state.current_phase,
                to: target,
            });
        }

        if target == state.current_phase {
            return Err(StateError::InvalidTransition {
                from: state.current_phase,
                to: target,
            });
        }

        let record = RevisitRecord {
            from_phase: state.current_phase,
            to_phase: target,
            at: Utc::now(),
        };

        info!(
            session_id = %state.session_id,
            from = %record.from_phase,
            to = %record.to_phase,
            "phase revisit — no data cleared"
        );

        state.revisit_history.push(record);
        state.revisit_target = Some(target);
        state.current_phase = target;
        state.updated_at = Utc::now();

        Ok(())
    }
}
