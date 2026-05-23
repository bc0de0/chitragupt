use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use super::phase::SessionPhase;
use crate::error::{Result, StateError};

// ── Supporting types ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Actor {
    pub id: Uuid,
    pub name: String,
    pub role: String,
    pub is_decision_maker: bool,
}

impl Actor {
    pub fn from_entity_value(value: &str, _confidence: f32) -> Self {
        let lower = value.to_lowercase();
        let is_dm = lower.contains("final approver")
            || lower.contains("decision maker")
            || lower.contains("decision_maker")
            || lower.contains("sign-off")
            || lower.contains("sign off");

        let (name, role) = value
            .split_once(',')
            .map(|(n, r)| {
                (
                    n.trim().to_string(),
                    r.trim().trim_start_matches('—').trim().to_string(),
                )
            })
            .unwrap_or_else(|| (value.trim().to_string(), String::new()));

        Actor {
            id: Uuid::new_v4(),
            name,
            role,
            is_decision_maker: is_dm,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum RequirementType {
    Functional,
    NonFunctional,
    Constraint,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DraftRequirement {
    pub id: String,
    pub description: String,
    pub actor_id: Option<Uuid>,
    pub requirement_type: RequirementType,
    pub confidence: f32,
    pub source_chunk_ids: Vec<Uuid>,
}

impl DraftRequirement {
    pub fn from_entity(entity: &ExtractedEntity) -> Self {
        let lower = entity.value.to_lowercase();
        let req_type = if lower.contains("non_functional")
            || lower.contains("non-functional")
            || lower.contains("performance")
            || lower.contains("response time")
            || lower.contains("availability")
            || lower.contains("concurrent")
            || lower.contains("uptime")
            || lower.contains("sla")
            || lower.contains("latency")
        {
            RequirementType::NonFunctional
        } else {
            RequirementType::Functional
        };

        DraftRequirement {
            id: format!("REQ-{}", Uuid::new_v4().simple()),
            description: entity.value.clone(),
            actor_id: None,
            requirement_type: req_type,
            confidence: entity.confidence,
            source_chunk_ids: entity.source_chunk_ids.clone(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ConstraintType {
    Budget,
    Timeline,
    Technology,
    Regulatory,
    DataResidency,
    Other,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DraftConstraint {
    pub id: String,
    pub description: String,
    pub constraint_type: ConstraintType,
}

impl DraftConstraint {
    pub fn from_entity_value(value: &str) -> Self {
        let lower = value.to_lowercase();
        let constraint_type = if lower.contains("timeline")
            || lower.contains("deadline")
            || lower.contains("delivery")
            || lower.contains("q1")
            || lower.contains("q2")
            || lower.contains("q3")
            || lower.contains("q4")
            || lower.contains("end of")
        {
            ConstraintType::Timeline
        } else if lower.contains("budget")
            || lower.contains(" £")
            || lower.contains(" $")
            || lower.contains("cost")
        {
            ConstraintType::Budget
        } else if lower.contains("gdpr")
            || lower.contains("hipaa")
            || lower.contains("fca")
            || lower.contains("regulatory")
            || lower.contains("compliance")
            || lower.contains("iso ")
        {
            ConstraintType::Regulatory
        } else if lower.contains("data residency")
            || lower.contains("sovereignty")
            || lower.contains("must reside")
        {
            ConstraintType::DataResidency
        } else if lower.contains("technology")
            || lower.contains("platform")
            || lower.contains("stack")
            || lower.contains("azure")
            || lower.contains("aws ")
            || lower.contains("gcp")
        {
            ConstraintType::Technology
        } else {
            ConstraintType::Other
        };

        DraftConstraint {
            id: format!("CON-{}", Uuid::new_v4().simple()),
            description: value.to_string(),
            constraint_type,
        }
    }
}

/// AC status change produced by the Python pipeline and applied back to SessionState.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcUpdate {
    pub criterion_id: String,
    pub met: bool,
    pub evidence: String,
}

/// Entity extracted by EntityExtractorNode from the BA's message.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedEntity {
    pub entity_type: String, // actor | requirement | constraint | assumption | gap
    pub value: String,
    pub confidence: f32,
    pub source: String, // conversation | document
    pub source_chunk_ids: Vec<Uuid>,
}

/// One entry in the REVISIT audit trail.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RevisitRecord {
    pub from_phase: SessionPhase,
    pub to_phase: SessionPhase,
    pub at: DateTime<Utc>,
}

// ── SessionState ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionState {
    pub session_id: Uuid,
    pub workspace_id: Uuid,
    pub project_id: Uuid,
    pub current_phase: SessionPhase,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,

    // Phase 1 — Problem Intake
    pub problem_statement: Option<String>,
    pub business_domain: Option<String>,
    pub primary_goal: Option<String>,
    pub pain_points: Vec<String>,
    pub scope_boundaries: Vec<String>,

    // Phase 2 — Stakeholder Discovery
    pub actors: Vec<Actor>,
    pub external_systems: Vec<String>,
    pub success_definition: Option<String>,
    pub regulatory_context: Option<String>,

    // Phase 3 — Requirement Elicitation
    pub requirements: Vec<DraftRequirement>,

    // Phase 4 — Constraint Capture
    pub constraints: Vec<DraftConstraint>,
    pub assumptions: Vec<String>,

    // Phase 5 — Architecture Alignment
    pub architecture_approach: Option<String>,
    pub deployment_environment: Option<String>,

    // Any phase — open questions / gaps
    pub open_questions: Vec<String>,

    // AC tracking (written by apply_ac_update)
    pub ac_met: Vec<String>,
    pub ac_waived: Vec<String>,

    // Upload gate tracking
    pub documents_indexed: Vec<Uuid>,
    pub upload_gates_resolved: Vec<String>,
    pub upload_gates_waived: Vec<String>,

    // Phase 6 — Output artifacts
    pub brd_artifact_id: Option<Uuid>,
    pub hld_artifact_id: Option<Uuid>,
    pub client_signature_confirmed: bool,

    // REVISIT support
    pub revisit_target: Option<SessionPhase>,
    pub revisit_history: Vec<RevisitRecord>,

    // Cost tracking
    pub total_llm_cost_usd: f64,
    pub turn_count: u32,
}

impl SessionState {
    pub fn new(workspace_id: Uuid, project_id: Uuid) -> Self {
        let now = Utc::now();
        Self {
            session_id: Uuid::new_v4(),
            workspace_id,
            project_id,
            current_phase: SessionPhase::ProblemIntake,
            created_at: now,
            updated_at: now,

            problem_statement: None,
            business_domain: None,
            primary_goal: None,
            pain_points: Vec::new(),
            scope_boundaries: Vec::new(),

            actors: Vec::new(),
            external_systems: Vec::new(),
            success_definition: None,
            regulatory_context: None,

            requirements: Vec::new(),

            constraints: Vec::new(),
            assumptions: Vec::new(),

            architecture_approach: None,
            deployment_environment: None,

            open_questions: Vec::new(),

            ac_met: Vec::new(),
            ac_waived: Vec::new(),

            documents_indexed: Vec::new(),
            upload_gates_resolved: Vec::new(),
            upload_gates_waived: Vec::new(),

            brd_artifact_id: None,
            hld_artifact_id: None,
            client_signature_confirmed: false,

            revisit_target: None,
            revisit_history: Vec::new(),

            total_llm_cost_usd: 0.0,
            turn_count: 0,
        }
    }

    /// Apply an AC status update from the Python pipeline.
    /// If `met` is true: adds criterion_id to ac_met, removes from ac_waived.
    /// If `met` is false: removes criterion_id from ac_met (waived status is unchanged).
    pub fn apply_ac_update(&mut self, update: &AcUpdate) {
        if update.met {
            if !self.ac_met.contains(&update.criterion_id) {
                self.ac_met.push(update.criterion_id.clone());
            }
            self.ac_waived.retain(|id| id != &update.criterion_id);
        } else {
            self.ac_met.retain(|id| id != &update.criterion_id);
        }
        self.updated_at = Utc::now();
    }

    /// Route an extracted entity to the appropriate session field.
    /// Returns Err if entity_type is not one of the known types.
    pub fn apply_entity(&mut self, entity: &ExtractedEntity) -> Result<()> {
        match entity.entity_type.as_str() {
            "actor" => {
                self.actors
                    .push(Actor::from_entity_value(&entity.value, entity.confidence));
            }
            "requirement" => {
                self.requirements
                    .push(DraftRequirement::from_entity(entity));
            }
            "constraint" => {
                self.constraints
                    .push(DraftConstraint::from_entity_value(&entity.value));
            }
            "assumption" => {
                if !self.assumptions.contains(&entity.value) {
                    self.assumptions.push(entity.value.clone());
                }
            }
            "gap" => {
                if !self.open_questions.contains(&entity.value) {
                    self.open_questions.push(entity.value.clone());
                }
            }
            other => {
                return Err(StateError::UnknownEntityType {
                    entity_type: other.to_string(),
                });
            }
        }
        self.updated_at = Utc::now();
        Ok(())
    }
}
