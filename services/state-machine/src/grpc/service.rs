//! StateEngineService — tonic gRPC implementation of the StateEngine service.
//!
//! Session state is held in an in-memory Arc<RwLock<HashMap>> for Sprint 1.
//! TODO(sprint2): persist to Redis (session:{workspace_id}:{session_id}:state)
//! and load on first access so the service can restart without losing state.

use std::collections::HashMap;
use std::sync::Arc;

use tokio::sync::RwLock;
use tonic::{Request, Response, Status};
use tracing::{info, warn};
use uuid::Uuid;

use crate::error::StateError;
use crate::gates::manager::GateManager;
use crate::state::phase::SessionPhase;
use crate::state::session::{AcUpdate, ExtractedEntity, SessionState};
use crate::state::transition::TransitionEngine;

use super::proto::common::{AcUpdateProto, EntityProto, SessionStateProto};
use super::proto::state::{
    state_engine_server::StateEngine, CreateSessionRequest, CreateSessionResponse,
    RevisitRequest, RevisitResponse, SessionQuery, TransitionRequest, TransitionResponse,
    TurnResultRequest, TurnResultResponse,
};

// ---------------------------------------------------------------------------
// Service struct
// ---------------------------------------------------------------------------

pub struct StateEngineService {
    sessions:     Arc<RwLock<HashMap<Uuid, SessionState>>>,
    gate_manager: Arc<GateManager>,
}

impl StateEngineService {
    pub fn new() -> Self {
        Self {
            sessions:     Arc::new(RwLock::new(HashMap::new())),
            gate_manager: Arc::new(GateManager::new()),
        }
    }
}

impl Default for StateEngineService {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Trait implementation
// ---------------------------------------------------------------------------

#[tonic::async_trait]
impl StateEngine for StateEngineService {
    // ── CreateSession ───────────────────────────────────────────────────────

    async fn create_session(
        &self,
        request: Request<CreateSessionRequest>,
    ) -> Result<Response<CreateSessionResponse>, Status> {
        let req = request.into_inner();
        let workspace_id = parse_uuid(&req.workspace_id, "workspace_id")?;
        let project_id   = parse_uuid(&req.project_id,   "project_id")?;

        let state = SessionState::new(workspace_id, project_id);
        let session_id    = state.session_id;
        let current_phase = state.current_phase.to_string();

        self.sessions.write().await.insert(session_id, state);

        info!(
            %session_id,
            %workspace_id,
            "session created"
        );

        Ok(Response::new(CreateSessionResponse {
            session_id:    session_id.to_string(),
            current_phase,
        }))
    }

    // ── GetSessionState ─────────────────────────────────────────────────────

    async fn get_session_state(
        &self,
        request: Request<SessionQuery>,
    ) -> Result<Response<SessionStateProto>, Status> {
        let req        = request.into_inner();
        let session_id = parse_uuid(&req.session_id, "session_id")?;

        let sessions = self.sessions.read().await;
        let state = sessions
            .get(&session_id)
            .ok_or_else(|| Status::not_found(format!("session {session_id} not found")))?;

        Ok(Response::new(state_to_proto(state)))
    }

    // ── ApplyTurnResult ─────────────────────────────────────────────────────

    async fn apply_turn_result(
        &self,
        request: Request<TurnResultRequest>,
    ) -> Result<Response<TurnResultResponse>, Status> {
        let req        = request.into_inner();
        let session_id = parse_uuid(&req.session_id, "session_id")?;

        let mut sessions = self.sessions.write().await;
        let state = sessions
            .get_mut(&session_id)
            .ok_or_else(|| Status::not_found(format!("session {session_id} not found")))?;

        // Apply extracted entities
        for entity_proto in &req.entities {
            let entity = proto_to_entity(entity_proto);
            if let Err(e) = state.apply_entity(&entity) {
                warn!(%session_id, "apply_entity error: {}", e);
            }
        }

        // Apply AC updates
        for ac_proto in &req.ac_updates {
            let ac_update = proto_to_ac_update(ac_proto);
            state.apply_ac_update(&ac_update);
        }

        // Increment cost and turn counter
        state.total_llm_cost_usd += req.cost_usd;
        state.turn_count          += req.turn_count_delta.max(0) as u32;

        // Evaluate current AC for the response
        let ac_result       = state.current_phase.evaluate_ac(state);
        let transition_ready = ac_result.transition_ready;
        let unmet_ac_count   = ac_result.unmet_count() as i32;
        let current_phase    = state.current_phase.to_string();

        info!(
            %session_id,
            entities = req.entities.len(),
            ac_updates = req.ac_updates.len(),
            %transition_ready,
            "turn result applied"
        );

        Ok(Response::new(TurnResultResponse {
            current_phase,
            transition_ready,
            unmet_ac_count,
        }))
    }

    // ── RequestTransition ───────────────────────────────────────────────────

    async fn request_transition(
        &self,
        request: Request<TransitionRequest>,
    ) -> Result<Response<TransitionResponse>, Status> {
        let req        = request.into_inner();
        let session_id = parse_uuid(&req.session_id, "session_id")?;
        let target: SessionPhase = req.target_phase
            .parse()
            .map_err(|_| Status::invalid_argument(format!("unknown phase: {}", req.target_phase)))?;

        let mut sessions = self.sessions.write().await;
        let state = sessions
            .get_mut(&session_id)
            .ok_or_else(|| Status::not_found(format!("session {session_id} not found")))?;

        match TransitionEngine::attempt(state, target, &self.gate_manager) {
            Ok(()) => {
                state.current_phase = target;
                info!(%session_id, phase = %target, "phase transition approved");
                Ok(Response::new(TransitionResponse {
                    approved:      true,
                    error_message: String::new(),
                    current_phase: target.to_string(),
                }))
            }
            Err(e) => {
                warn!(%session_id, "transition blocked: {}", e);
                Ok(Response::new(TransitionResponse {
                    approved:      false,
                    error_message: e.to_string(),
                    current_phase: state.current_phase.to_string(),
                }))
            }
        }
    }

    // ── RevisitPhase ────────────────────────────────────────────────────────

    async fn revisit_phase(
        &self,
        request: Request<RevisitRequest>,
    ) -> Result<Response<RevisitResponse>, Status> {
        let req        = request.into_inner();
        let session_id = parse_uuid(&req.session_id, "session_id")?;
        let target: SessionPhase = req.target_phase
            .parse()
            .map_err(|_| Status::invalid_argument(format!("unknown phase: {}", req.target_phase)))?;

        let mut sessions = self.sessions.write().await;
        let state = sessions
            .get_mut(&session_id)
            .ok_or_else(|| Status::not_found(format!("session {session_id} not found")))?;

        match TransitionEngine::revisit(state, target) {
            Ok(()) => {
                info!(%session_id, phase = %target, "revisit approved");
                Ok(Response::new(RevisitResponse {
                    ok:            true,
                    error_message: String::new(),
                    current_phase: target.to_string(),
                }))
            }
            Err(e) => {
                warn!(%session_id, "revisit blocked: {}", e);
                Ok(Response::new(RevisitResponse {
                    ok:            false,
                    error_message: e.to_string(),
                    current_phase: state.current_phase.to_string(),
                }))
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Mapping helpers
// ---------------------------------------------------------------------------

fn parse_uuid(s: &str, field: &str) -> Result<Uuid, Status> {
    s.parse::<Uuid>()
        .map_err(|_| Status::invalid_argument(format!("invalid {field}: {s}")))
}

fn state_to_proto(state: &SessionState) -> SessionStateProto {
    let state_json = serde_json::to_string(state).unwrap_or_default();
    SessionStateProto {
        session_id:         state.session_id.to_string(),
        workspace_id:       state.workspace_id.to_string(),
        project_id:         state.project_id.to_string(),
        current_phase:      state.current_phase.to_string(),
        turn_count:         state.turn_count as i32,
        total_cost_usd:     state.total_llm_cost_usd,
        ac_met:             state.ac_met.clone(),
        ac_waived:          state.ac_waived.clone(),
        documents_indexed:  state.documents_indexed.iter().map(|u| u.to_string()).collect(),
        state_json,
    }
}

fn proto_to_entity(p: &EntityProto) -> ExtractedEntity {
    use uuid::Uuid;
    ExtractedEntity {
        entity_type:      p.entity_type.clone(),
        value:            p.value.clone(),
        confidence:       p.confidence,
        source:           p.source.clone(),
        source_chunk_ids: p
            .source_chunk_ids
            .iter()
            .filter_map(|s| s.parse::<Uuid>().ok())
            .collect(),
    }
}

fn proto_to_ac_update(p: &AcUpdateProto) -> AcUpdate {
    AcUpdate {
        criterion_id: p.criterion_id.clone(),
        met:          p.met,
        evidence:     p.evidence.clone(),
    }
}
