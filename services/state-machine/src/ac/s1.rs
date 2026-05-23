// AC-S1: PROBLEM_INTAKE → STAKEHOLDER_DISCOVERY
// Evaluates whether problem definition and intent ingestion are complete.

use crate::ac::result::AcResult;
use crate::state::session::SessionState;

pub fn evaluate(state: &SessionState) -> AcResult {
    AcResult::from_checks(
        vec![
            (
                "AC-S1-01",
                "Problem statement captured (min 50 words)",
                "Can you describe the business problem you're trying to solve in a few sentences?",
                state.problem_statement.is_some(),
            ),
            (
                "AC-S1-02",
                "Business domain identified",
                "What industry or business domain does this project operate in?",
                state.business_domain.is_some(),
            ),
            (
                "AC-S1-03",
                "Primary goal articulated",
                "What is the single most important outcome this project needs to achieve?",
                state.primary_goal.is_some(),
            ),
            (
                "AC-S1-04",
                "At least one pain point captured",
                "What is the biggest pain point the current process has that this system will fix?",
                !state.pain_points.is_empty(),
            ),
            (
                "AC-S1-05",
                "Scope boundary stated (in-scope or out-of-scope)",
                "Are there things you already know are explicitly out of scope for this project?",
                !state.scope_boundaries.is_empty(),
            ),
            (
                "AC-S1-U1",
                "Optional: existing system documentation or brief uploaded",
                "Do you have any existing documentation — a brief, a deck, or previous specs — you'd like to share?",
                !state.documents_indexed.is_empty(),
            ),
        ],
        &state.ac_met,
        &state.ac_waived,
    )
}
