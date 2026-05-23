# Session State Fixtures

JSON snapshots of `SessionState` at each phase boundary, used by state boundary integration tests (T-STATE-05 through T-STATE-15).

## Files

| File | Phase | Description |
|---|---|---|
| `phase1_all_ac_met.json` | ProblemIntake | All required ACs met — transition to Phase 2 ready |
| `phase1_one_ac_short.json` | ProblemIntake | AC-S1-03 unmet — transition to Phase 2 blocked |
| `phase2_all_ac_met.json` | StakeholderDiscovery | All required ACs met — transition to Phase 3 ready |
| `phase3_regulated_no_docs.json` | RequirementElicitation | Regulated domain, documents_indexed=[] — Phase 3→4 blocked |
| `phase3_regulated_one_doc.json` | RequirementElicitation | Regulated domain, one document indexed — Phase 3→4 allowed |
| `phase4_all_ac_met.json` | ConstraintCapture | All required ACs met — transition to Phase 5 ready |
| `phase5_signed_off.json` | ReviewAndSignOff | Session signed off — all forward transitions rejected |

These fixtures are populated during integration test setup via the `conftest.py` fixture that connects to the Rust state machine gRPC service.

## Format

```json
{
  "session_id": "test-state-XXX",
  "workspace_id": "test-workspace-001",
  "current_phase": "ProblemIntake",
  "ac_met": ["AC-S1-01", "AC-S1-02"],
  "ac_waived": [],
  "actors": [],
  "requirements": [],
  "constraints": [],
  "assumptions": [],
  "open_questions": [],
  "documents_indexed": [],
  "problem_statement": "Example problem statement.",
  "business_domain": null,
  "success_definition": null,
  "regulatory_context": null,
  "architecture_approach": null,
  "deployment_environment": null
}
```
