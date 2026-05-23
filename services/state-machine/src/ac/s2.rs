// AC-S2: STAKEHOLDER_DISCOVERY → REQUIREMENT_ELICITATION
// Evaluates whether the stakeholder map is sufficiently complete to begin requirements.

use crate::ac::result::AcResult;
use crate::state::session::SessionState;

pub fn evaluate(state: &SessionState) -> AcResult {
    AcResult::from_checks(
        vec![
            (
                "AC-S2-01",
                "At least two named actors identified",
                "Who are the main types of users that will interact with this system?",
                state.actors.len() >= 2,
            ),
            (
                "AC-S2-02",
                "Primary decision-maker identified",
                "Who is the single most important stakeholder that will sign off on this project?",
                state.actors.iter().any(|a| a.is_decision_maker),
            ),
            (
                "AC-S2-03",
                "At least one external system or integration identified",
                "Does this system need to connect with any existing tools, databases, or external services?",
                !state.external_systems.is_empty(),
            ),
            (
                "AC-S2-04",
                "Success definition from stakeholder perspective captured",
                "How will the client or key stakeholder know this project has been successful?",
                state.success_definition.is_some(),
            ),
            (
                "AC-S2-05",
                "Regulatory or compliance context noted (or explicitly none)",
                "Are there any regulatory, legal, or compliance requirements we need to be aware of?",
                state.regulatory_context.is_some(),
            ),
            (
                "AC-S2-U1",
                "Optional: org chart, stakeholder map, or RACI uploaded",
                "Do you have a stakeholder map, org chart, or RACI matrix you'd like to upload?",
                !state.documents_indexed.is_empty(),
            ),
        ],
        &state.ac_met,
        &state.ac_waived,
    )
}
