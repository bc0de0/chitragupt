// Tests for SessionState mutation methods: apply_entity, apply_ac_update, and revisit.

use chitragupt_state_machine::error::StateError;
use chitragupt_state_machine::state::phase::SessionPhase;
use chitragupt_state_machine::state::session::{AcUpdate, ExtractedEntity, SessionState};
use chitragupt_state_machine::state::transition::TransitionEngine;
use uuid::Uuid;

fn fresh() -> SessionState {
    SessionState::new(Uuid::new_v4(), Uuid::new_v4())
}

fn entity(entity_type: &str, value: &str) -> ExtractedEntity {
    ExtractedEntity {
        entity_type: entity_type.to_string(),
        value: value.to_string(),
        confidence: 1.0,
        source: "conversation".to_string(),
        source_chunk_ids: vec![],
    }
}

fn update(criterion_id: &str, met: bool) -> AcUpdate {
    AcUpdate {
        criterion_id: criterion_id.to_string(),
        met,
        evidence: String::new(),
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// apply_entity — actors
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn apply_entity_actor_appends_to_actors() {
    let mut s = fresh();
    s.apply_entity(&entity("actor", "Sarah Chen, CFO")).unwrap();
    assert_eq!(s.actors.len(), 1);
    assert_eq!(s.actors[0].name, "Sarah Chen");
}

#[test]
fn apply_entity_actor_parses_role_after_comma() {
    let mut s = fresh();
    s.apply_entity(&entity(
        "actor",
        "John Smith, VP Engineering — technical lead",
    ))
    .unwrap();
    assert_eq!(s.actors[0].name, "John Smith");
    assert!(s.actors[0].role.contains("VP Engineering"));
}

#[test]
fn apply_entity_actor_detects_decision_maker() {
    let mut s = fresh();
    s.apply_entity(&entity("actor", "Alice, CEO — final approver"))
        .unwrap();
    assert!(s.actors[0].is_decision_maker);
}

#[test]
fn apply_entity_actor_non_decision_maker_by_default() {
    let mut s = fresh();
    s.apply_entity(&entity("actor", "Bob, Developer")).unwrap();
    assert!(!s.actors[0].is_decision_maker);
}

#[test]
fn apply_entity_multiple_actors_accumulate() {
    let mut s = fresh();
    s.apply_entity(&entity("actor", "Alice, CEO")).unwrap();
    s.apply_entity(&entity("actor", "Bob, Developer")).unwrap();
    assert_eq!(s.actors.len(), 2);
}

// ─────────────────────────────────────────────────────────────────────────────
// apply_entity — requirements
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn apply_entity_requirement_appends_to_requirements() {
    let mut s = fresh();
    s.apply_entity(&entity(
        "requirement",
        "System must generate PDF reports on demand [functional, must]",
    ))
    .unwrap();
    assert_eq!(s.requirements.len(), 1);
}

#[test]
fn apply_entity_requirement_classifies_functional() {
    use chitragupt_state_machine::state::session::RequirementType;
    let mut s = fresh();
    s.apply_entity(&entity("requirement", "Users can upload a CSV file"))
        .unwrap();
    assert_eq!(
        s.requirements[0].requirement_type,
        RequirementType::Functional
    );
}

#[test]
fn apply_entity_requirement_classifies_non_functional() {
    use chitragupt_state_machine::state::session::RequirementType;
    let mut s = fresh();
    s.apply_entity(&entity(
        "requirement",
        "System response time must be under 2 seconds [non_functional]",
    ))
    .unwrap();
    assert_eq!(
        s.requirements[0].requirement_type,
        RequirementType::NonFunctional
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// apply_entity — constraints
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn apply_entity_constraint_appends_to_constraints() {
    let mut s = fresh();
    s.apply_entity(&entity(
        "constraint",
        "Budget: approximately £150,000 [budget]",
    ))
    .unwrap();
    assert_eq!(s.constraints.len(), 1);
}

#[test]
fn apply_entity_constraint_classifies_budget() {
    use chitragupt_state_machine::state::session::ConstraintType;
    let mut s = fresh();
    s.apply_entity(&entity("constraint", "Total budget is $200k"))
        .unwrap();
    assert_eq!(s.constraints[0].constraint_type, ConstraintType::Budget);
}

#[test]
fn apply_entity_constraint_classifies_timeline() {
    use chitragupt_state_machine::state::session::ConstraintType;
    let mut s = fresh();
    s.apply_entity(&entity("constraint", "Delivery deadline is end of Q3"))
        .unwrap();
    assert_eq!(s.constraints[0].constraint_type, ConstraintType::Timeline);
}

#[test]
fn apply_entity_constraint_classifies_regulatory() {
    use chitragupt_state_machine::state::session::ConstraintType;
    let mut s = fresh();
    s.apply_entity(&entity("constraint", "GDPR compliance required"))
        .unwrap();
    assert_eq!(s.constraints[0].constraint_type, ConstraintType::Regulatory);
}

// ─────────────────────────────────────────────────────────────────────────────
// apply_entity — assumptions and gaps
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn apply_entity_assumption_appends() {
    let mut s = fresh();
    s.apply_entity(&entity("assumption", "Client has an existing SSO provider"))
        .unwrap();
    assert_eq!(s.assumptions.len(), 1);
}

#[test]
fn apply_entity_assumption_deduplicates() {
    let mut s = fresh();
    let e = entity("assumption", "Client has an existing SSO provider");
    s.apply_entity(&e).unwrap();
    s.apply_entity(&e).unwrap();
    assert_eq!(s.assumptions.len(), 1);
}

#[test]
fn apply_entity_gap_appends_to_open_questions() {
    let mut s = fresh();
    s.apply_entity(&entity("gap", "Data owner not identified — BA to confirm"))
        .unwrap();
    assert_eq!(s.open_questions.len(), 1);
}

#[test]
fn apply_entity_gap_deduplicates() {
    let mut s = fresh();
    let e = entity("gap", "Data owner not identified");
    s.apply_entity(&e).unwrap();
    s.apply_entity(&e).unwrap();
    assert_eq!(s.open_questions.len(), 1);
}

// ─────────────────────────────────────────────────────────────────────────────
// apply_entity — unknown type
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn apply_entity_unknown_type_returns_err() {
    let mut s = fresh();
    let result = s.apply_entity(&entity("spaceship", "USS Enterprise"));
    assert!(matches!(result, Err(StateError::UnknownEntityType { .. })));
}

#[test]
fn apply_entity_unknown_type_does_not_mutate_state() {
    let mut s = fresh();
    s.apply_entity(&entity("invalid", "something")).unwrap_err();
    assert!(s.actors.is_empty());
    assert!(s.requirements.is_empty());
    assert!(s.constraints.is_empty());
}

// ─────────────────────────────────────────────────────────────────────────────
// apply_ac_update
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn apply_ac_update_marks_criterion_as_met() {
    let mut s = fresh();
    s.apply_ac_update(&update("AC-S1-01", true));
    assert!(s.ac_met.contains(&"AC-S1-01".to_string()));
}

#[test]
fn apply_ac_update_met_does_not_duplicate() {
    let mut s = fresh();
    s.apply_ac_update(&update("AC-S1-01", true));
    s.apply_ac_update(&update("AC-S1-01", true));
    assert_eq!(s.ac_met.iter().filter(|id| *id == "AC-S1-01").count(), 1);
}

#[test]
fn apply_ac_update_unmet_removes_from_ac_met() {
    let mut s = fresh();
    s.apply_ac_update(&update("AC-S1-01", true));
    s.apply_ac_update(&update("AC-S1-01", false));
    assert!(!s.ac_met.contains(&"AC-S1-01".to_string()));
}

#[test]
fn apply_ac_update_met_clears_from_waived() {
    let mut s = fresh();
    s.ac_waived.push("AC-S1-01".to_string());
    s.apply_ac_update(&update("AC-S1-01", true));
    assert!(!s.ac_waived.contains(&"AC-S1-01".to_string()));
    assert!(s.ac_met.contains(&"AC-S1-01".to_string()));
}

#[test]
fn apply_ac_update_unmet_leaves_waived_unchanged() {
    let mut s = fresh();
    s.ac_waived.push("AC-S2-01".to_string());
    s.apply_ac_update(&update("AC-S2-01", false));
    // waived should still be there — only met=true clears waived
    assert!(s.ac_waived.contains(&"AC-S2-01".to_string()));
}

#[test]
fn apply_ac_update_updates_updated_at() {
    let mut s = fresh();
    let before = s.updated_at;
    std::thread::sleep(std::time::Duration::from_millis(5));
    s.apply_ac_update(&update("AC-S1-01", true));
    assert!(s.updated_at > before);
}

// ─────────────────────────────────────────────────────────────────────────────
// revisit
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn revisit_changes_current_phase_to_target() {
    let mut s = fresh();
    s.current_phase = SessionPhase::RequirementElicitation;
    TransitionEngine::revisit(&mut s, SessionPhase::StakeholderDiscovery).unwrap();
    assert_eq!(s.current_phase, SessionPhase::StakeholderDiscovery);
}

#[test]
fn revisit_preserves_actors() {
    let mut s = fresh();
    s.actors
        .push(chitragupt_state_machine::state::session::Actor {
            id: Uuid::new_v4(),
            name: "Alice".into(),
            role: "CEO".into(),
            is_decision_maker: true,
        });
    s.current_phase = SessionPhase::RequirementElicitation;
    TransitionEngine::revisit(&mut s, SessionPhase::StakeholderDiscovery).unwrap();
    assert_eq!(s.actors.len(), 1);
}

#[test]
fn revisit_preserves_requirements() {
    let mut s = fresh();
    s.requirements
        .push(chitragupt_state_machine::state::session::DraftRequirement {
            id: "REQ-001".into(),
            description: "Upload PDF".into(),
            actor_id: None,
            requirement_type: chitragupt_state_machine::state::session::RequirementType::Functional,
            confidence: 1.0,
            source_chunk_ids: vec![],
        });
    s.current_phase = SessionPhase::ConstraintCapture;
    TransitionEngine::revisit(&mut s, SessionPhase::ProblemIntake).unwrap();
    assert_eq!(s.requirements.len(), 1);
}

#[test]
fn revisit_records_history_entry() {
    let mut s = fresh();
    s.current_phase = SessionPhase::RequirementElicitation;
    TransitionEngine::revisit(&mut s, SessionPhase::ProblemIntake).unwrap();
    assert_eq!(s.revisit_history.len(), 1);
    assert_eq!(
        s.revisit_history[0].from_phase,
        SessionPhase::RequirementElicitation
    );
    assert_eq!(s.revisit_history[0].to_phase, SessionPhase::ProblemIntake);
}

#[test]
fn revisit_sets_revisit_target() {
    let mut s = fresh();
    s.current_phase = SessionPhase::ConstraintCapture;
    TransitionEngine::revisit(&mut s, SessionPhase::StakeholderDiscovery).unwrap();
    assert_eq!(s.revisit_target, Some(SessionPhase::StakeholderDiscovery));
}

#[test]
fn revisit_to_same_phase_returns_err() {
    let mut s = fresh();
    s.current_phase = SessionPhase::StakeholderDiscovery;
    let result = TransitionEngine::revisit(&mut s, SessionPhase::StakeholderDiscovery);
    assert!(matches!(result, Err(StateError::InvalidTransition { .. })));
}

#[test]
fn revisit_to_signed_off_returns_err() {
    let mut s = fresh();
    s.current_phase = SessionPhase::ReviewAndSignOff;
    let result = TransitionEngine::revisit(&mut s, SessionPhase::SignedOff);
    assert!(matches!(result, Err(StateError::InvalidTransition { .. })));
}

#[test]
fn revisit_does_not_clear_ac_met() {
    let mut s = fresh();
    s.ac_met.push("AC-S1-01".to_string());
    s.current_phase = SessionPhase::RequirementElicitation;
    TransitionEngine::revisit(&mut s, SessionPhase::ProblemIntake).unwrap();
    assert!(s.ac_met.contains(&"AC-S1-01".to_string()));
}

#[test]
fn revisit_updates_updated_at() {
    let mut s = fresh();
    s.current_phase = SessionPhase::RequirementElicitation;
    let before = s.updated_at;
    std::thread::sleep(std::time::Duration::from_millis(5));
    TransitionEngine::revisit(&mut s, SessionPhase::ProblemIntake).unwrap();
    assert!(s.updated_at > before);
}
