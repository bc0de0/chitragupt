// AC-S3: REQUIREMENT_ELICITATION → CONSTRAINT_CAPTURE
// Evaluates whether functional and non-functional requirements are sufficiently elicited.
// AC-S3-U1 is a hard gate for regulated domains — also enforced by GateManager.

use crate::ac::result::AcResult;
use crate::state::session::{RequirementType, SessionState};

pub fn evaluate(state: &SessionState) -> AcResult {
    let functional_count = state
        .requirements
        .iter()
        .filter(|r| r.requirement_type == RequirementType::Functional)
        .count();

    let has_nonfunctional = state
        .requirements
        .iter()
        .any(|r| r.requirement_type == RequirementType::NonFunctional);

    // Every requirement must reference an actor for this criterion to be met.
    let all_linked =
        !state.requirements.is_empty() && state.requirements.iter().all(|r| r.actor_id.is_some());

    // Regulated domain gate: met when documents uploaded, or explicitly waived.
    // regulatory_context.is_none() means the domain hasn't been confirmed yet — gate stays unmet.
    // The GateManager enforces the hard block for confirmed regulated domains.
    let regulated_gate_met =
        !state.documents_indexed.is_empty() || state.ac_waived.iter().any(|w| w == "AC-S3-U1");

    AcResult::from_checks(
        vec![
            (
                "AC-S3-01",
                "Minimum five functional requirements captured",
                "Let's keep going — what else does the system need to do? Walk me through a typical user workflow.",
                functional_count >= 5,
            ),
            (
                "AC-S3-02",
                "At least one non-functional requirement captured (performance, security, availability)",
                "Are there any performance or reliability targets — like response times, uptime SLAs, or concurrent user counts?",
                has_nonfunctional,
            ),
            (
                "AC-S3-03",
                "Each requirement linked to at least one actor",
                "Who specifically needs this feature — which user role does it serve?",
                all_linked,
            ),
            (
                "AC-S3-04",
                "No unresolved requirement conflicts flagged as open",
                "Earlier we noted a potential conflict between two requirements — has that been resolved?",
                // Must be explicitly confirmed — empty open_questions on fresh session is not a resolved state.
                false,
            ),
            (
                "AC-S3-05",
                "At least one acceptance criterion written for the top-priority requirement",
                "For the most critical requirement, how would you test that it works correctly?",
                // Must be explicitly confirmed via AcUpdate — no direct field maps to this.
                false,
            ),
            (
                "AC-S3-U1",
                "HARD GATE if regulated domain: at least one source document uploaded",
                "This is a regulated domain project. Please upload at least one reference document before we continue.",
                regulated_gate_met,
            ),
            (
                "AC-S3-U2",
                "Optional: existing requirements doc, user stories, or process flow uploaded",
                "Do you have existing user stories, process flow diagrams, or a requirements document to share?",
                !state.documents_indexed.is_empty(),
            ),
        ],
        &state.ac_met,
        &state.ac_waived,
    )
}
