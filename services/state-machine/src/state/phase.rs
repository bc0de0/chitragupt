use serde::{Deserialize, Serialize};

use crate::ac::result::AcResult;
use crate::state::session::SessionState;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SessionPhase {
    ProblemIntake,
    StakeholderDiscovery,
    RequirementElicitation,
    ConstraintCapture,
    ArchitectureAlignment,
    ReviewAndSignOff,
    SignedOff,
}

impl SessionPhase {
    pub fn valid_transitions(&self) -> &'static [SessionPhase] {
        match self {
            SessionPhase::ProblemIntake => &[SessionPhase::StakeholderDiscovery],
            SessionPhase::StakeholderDiscovery => &[SessionPhase::RequirementElicitation],
            SessionPhase::RequirementElicitation => &[SessionPhase::ConstraintCapture],
            SessionPhase::ConstraintCapture => &[SessionPhase::ArchitectureAlignment],
            SessionPhase::ArchitectureAlignment => &[SessionPhase::ReviewAndSignOff],
            SessionPhase::ReviewAndSignOff => &[SessionPhase::SignedOff],
            SessionPhase::SignedOff => &[],
        }
    }

    pub fn is_terminal(&self) -> bool {
        *self == SessionPhase::SignedOff
    }

    pub fn evaluate_ac(&self, state: &SessionState) -> AcResult {
        match self {
            SessionPhase::ProblemIntake => crate::ac::s1::evaluate(state),
            SessionPhase::StakeholderDiscovery => crate::ac::s2::evaluate(state),
            SessionPhase::RequirementElicitation => crate::ac::s3::evaluate(state),
            SessionPhase::ConstraintCapture => crate::ac::s4::evaluate(state),
            SessionPhase::ArchitectureAlignment => crate::ac::s5::evaluate(state),
            SessionPhase::ReviewAndSignOff => crate::ac::s6::evaluate(state),
            SessionPhase::SignedOff => AcResult {
                criteria: vec![],
                gaps: vec![],
                transition_ready: false,
            },
        }
    }

    pub fn display_name(&self) -> &'static str {
        match self {
            SessionPhase::ProblemIntake => "Problem Intake",
            SessionPhase::StakeholderDiscovery => "Stakeholder Discovery",
            SessionPhase::RequirementElicitation => "Requirement Elicitation",
            SessionPhase::ConstraintCapture => "Constraint Capture",
            SessionPhase::ArchitectureAlignment => "Architecture Alignment",
            SessionPhase::ReviewAndSignOff => "Review & Sign-Off",
            SessionPhase::SignedOff => "Signed Off",
        }
    }
}

impl std::fmt::Display for SessionPhase {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.display_name())
    }
}

impl std::str::FromStr for SessionPhase {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "ProblemIntake" | "Problem Intake" => Ok(SessionPhase::ProblemIntake),
            "StakeholderDiscovery" | "Stakeholder Discovery" => Ok(SessionPhase::StakeholderDiscovery),
            "RequirementElicitation" | "Requirement Elicitation" => Ok(SessionPhase::RequirementElicitation),
            "ConstraintCapture" | "Constraint Capture" => Ok(SessionPhase::ConstraintCapture),
            "ArchitectureAlignment" | "Architecture Alignment" => Ok(SessionPhase::ArchitectureAlignment),
            "ReviewAndSignOff" | "Review & Sign-Off" => Ok(SessionPhase::ReviewAndSignOff),
            "SignedOff" | "Signed Off" => Ok(SessionPhase::SignedOff),
            _ => Err(format!("unknown phase: {s}")),
        }
    }
}
