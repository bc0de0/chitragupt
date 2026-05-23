// AC-S5: ARCHITECTURE_ALIGNMENT → REVIEW_AND_SIGN_OFF
// Evaluates whether architecture decisions are captured and the BRD/HLD can be generated.
// AC-S5-04 and AC-S5-U1 must be confirmed via explicit AcUpdate from Python.

use crate::ac::result::AcResult;
use crate::state::session::SessionState;

pub fn evaluate(state: &SessionState) -> AcResult {
    AcResult::from_checks(
        vec![
            (
                "AC-S5-01",
                "High-level architecture approach agreed (monolith / microservices / serverless / hybrid)",
                "What is the preferred architectural style — monolith, microservices, serverless, or a hybrid?",
                state.architecture_approach.is_some(),
            ),
            (
                "AC-S5-02",
                "Deployment environment decided (cloud provider / on-premise / hybrid)",
                "Where will this system be deployed — which cloud provider, or is on-premise required?",
                state.deployment_environment.is_some(),
            ),
            (
                "AC-S5-03",
                "Integration points mapped to concrete systems",
                "For each integration we identified, do we know the specific system name and access method?",
                !state.external_systems.is_empty(),
            ),
            (
                "AC-S5-04",
                "Data model reviewed at entity level",
                "Are there key data entities we haven't discussed yet — things the system needs to store or track?",
                // Must be explicitly confirmed via AcUpdate.
                false,
            ),
            (
                "AC-S5-05",
                "No HARD GATE upload requirements outstanding",
                "We still have required documents pending — let's resolve those before generating the BRD.",
                // Must be explicitly confirmed via AcUpdate when Python resolves all upload gates.
                false,
            ),
            (
                "AC-S5-U1",
                "REQUIRED PROMPT: HLD draft generated and BA-reviewed",
                "I've generated a draft High-Level Architecture diagram. Does this look correct before we finalize?",
                // Must be explicitly confirmed via AcUpdate after HLD generation.
                false,
            ),
            (
                "AC-S5-U2",
                "Optional: third-party API documentation or integration specs uploaded",
                "Do you have API documentation or integration specs for the external systems we've identified?",
                !state.documents_indexed.is_empty(),
            ),
        ],
        &state.ac_met,
        &state.ac_waived,
    )
}
