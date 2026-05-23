use thiserror::Error;
use uuid::Uuid;

use crate::state::phase::SessionPhase;

#[derive(Debug, Error)]
#[allow(dead_code)]
pub enum StateError {
    #[error("invalid transition: {from:?} → {to:?}")]
    InvalidTransition {
        from: SessionPhase,
        to: SessionPhase,
    },

    #[error("transition blocked by {gate_count} open hard gate(s)")]
    HardGateBlocking { gate_count: usize },

    #[error("acceptance criteria not met for transition: {unmet_count} criteria unmet")]
    AcNotMet { unmet_count: usize },

    #[error("session not found: {id}")]
    SessionNotFound { id: Uuid },

    #[error("session already in terminal state")]
    SessionTerminated,

    #[error("upload gate not satisfied: {gate_id}")]
    UploadGatePending { gate_id: String },

    #[error("unknown entity type: {entity_type}")]
    UnknownEntityType { entity_type: String },

    #[error("serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
}

pub type Result<T> = std::result::Result<T, StateError>;
