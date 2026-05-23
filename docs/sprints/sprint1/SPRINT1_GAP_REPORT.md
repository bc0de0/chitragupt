# Sprint 1 — Exit Criteria Gap Report

**Generated:** May 2026  
**Status:** Sprint 1 OPEN — 4 of 5 exit criteria unmet or partially met

This document is a point-in-time gap analysis against the five exit criteria defined in [Sprint 1 README](README.md). It identifies what exists, what is a skeleton, and what has not been started. It is a working document and should be deleted once all criteria are closed.

---

## Criteria Scorecard

| # | Exit Criterion | Status |
|---|---|---|
| 1 | BA session moves Problem Intake → confirmed requirements via conversation alone | PARTIAL |
| 2 | System surfaces exactly one next question or transition offer per turn, always | PARTIAL |
| 3 | Document at Checkpoint B is indexed, retrievable, and requirements carry provenance | PARTIAL |
| 4 | Regulated domain session cannot close Phase 3 without upload or explicit waiver | **DONE** |
| 5 | REVISIT requests handled without losing any captured data | NOT STARTED |

---

## Criterion 1 — End-to-End Conversational Flow

**What exists:**
- Rust state machine with full linear transition graph: ProblemIntake → StakeholderDiscovery → RequirementElicitation → ConstraintCapture → ArchitectureAlignment → ReviewAndSignOff → SignedOff
- AC evaluators for all six transitions (`ac/s1.rs` through `ac/s6.rs`)
- `TransitionEngine` that blocks on unmet AC and open hard gates
- Python `PipelineExecutor` skeleton that runs a LangGraph pipeline per turn

**What is a skeleton (TODOs in code):**
- `IntentClassifierNode` — classifies user turn into one of 8 intents; currently returns `"Clarification"` for every turn
- `EntityExtractorNode` — extracts phase-specific entities (actors, requirements, constraints); currently returns empty list
- `GapAnalyzerNode` — identifies highest-priority unmet AC and generates a suggested question; returns a terminal placeholder
- `GuidanceGeneratorNode` — streams the BA-facing response; emits one placeholder token

**What is missing entirely:**
- Session state mutation loop: `AcUpdate` entities produced by Python nodes must be applied back to the Rust `SessionState` fields (problem_statement, actors, requirements, constraints, etc.); without this, AC evaluators will never read real data and phases will never advance
- gRPC service layer: the Python executor is not wired to any request/response handler; no entry point exists for a client to send a message and receive a streamed response

**What is needed to close this criterion:**
1. Implement LLM calls in `IntentClassifierNode` and `EntityExtractorNode` (Haiku with phase-specific prompts)
2. Implement LLM call in `GapAnalyzerNode` (Sonnet evaluating current session state against phase AC)
3. Implement streaming in `GuidanceGeneratorNode` (Sonnet/Opus depending on phase and budget)
4. Build the `SessionState` update path so entity outputs from Python mutate the Rust session fields
5. Wire gRPC service layer so a message in → entities out → state updated → response streamed is a live end-to-end path

---

## Criterion 2 — Exactly One Next Question Per Turn

**What exists:**
- `GapResult` dataclass has a `suggested_question: str` field intended to carry the single next question
- `TurnResult` carries the full per-turn output including `gap_analysis`
- Architecture decision recorded in `LLM_ORCHESTRATION.md`: pipeline is linear; only one gap is surfaced per turn

**What is a skeleton:**
- `GapAnalyzerNode` is designed to call the gap evaluator and return exactly one `GapResult`, but the LLM call is not implemented; it currently returns a terminal placeholder that will never produce a real question
- `GuidanceGeneratorNode` is designed to read the gap and produce exactly one question or one transition offer, but the streaming call is not implemented

**What is missing entirely:**
- Enforcement rule: the guidance prompt must be written to instruct the model to produce exactly one question or exactly one transition offer — never both, never zero. This prompt does not exist yet.
- Test coverage verifying that every pipeline run produces exactly one guidance token stream (not zero, not two questions)

**What is needed to close this criterion:**
1. Implement `GapAnalyzerNode` LLM call
2. Write the `GuidanceGeneratorNode` system prompt with the single-question rule as a hard constraint
3. Add a pipeline-level integration test asserting single-question output across multiple simulated turns and phases

---

## Criterion 3 — Document Indexing, Retrieval, and Provenance

**What exists:**
- `SessionState.documents_indexed: Vec<Uuid>` tracks document IDs at the session level
- `ChunkRef` dataclass carries `document_id`, `section_title`, `page_number` for retrieval provenance
- `Entity.source_chunk_ids: list[str]` designed to link extracted entities back to document chunks
- `RAGRetrievalNode` skeleton with hybrid retrieval config (BM25 weight 0.3, dense weight 0.7, top-k 10 after rerank)
- `orchestration.yaml` has ingestion parameters (chunk size 512 tokens, overlap 64, min 50)

**What is a skeleton:**
- `RAGRetrievalNode` — typed retrieval path exists; currently returns empty list with TODO comment; no pgvector query, no BM25 query, no Voyage embedding call
- `BudgetTracker` — Redis `INCRBYFLOAT` call for atomic spend accumulation has a TODO; currently in-process only

**What is missing entirely:**
- Document upload handler: no HTTP or gRPC endpoint receives a file, chunks it, embeds it with Voyage, and inserts rows into pgvector
- Ingestion pipeline: chunk boundary logic, metadata extraction (document_id, page_number, section_title), tenant-scoped namespace in pgvector
- Provenance enforcement: no code currently traces from a requirement back to the chunk it was sourced from and surfaces that in the BRD. The field is defined in the data model but nothing writes to it.
- Database schema: `DATABASE.md` defines the strategy but no migration files or schema SQL exists in the repo

**What is needed to close this criterion:**
1. Implement document ingestion: upload endpoint → chunking → Voyage embedding → pgvector insert with metadata
2. Implement `RAGRetrievalNode`: Voyage embed query → pgvector ANN → BM25 → hybrid merge → top-k rerank
3. Ensure `EntityExtractorNode` writes `source_chunk_ids` from the chunks that evidence the extracted entity
4. Add provenance assertion to Phase 3 AC check: at least one requirement with non-empty `source_chunk_ids` must exist when `documents_indexed` is non-empty

---

## Criterion 4 — Regulated Domain Hard Gate (Phase 3)

**Status: DONE.**

`GateManager` implements `GATE-REGULATED-SOURCE-DOC`. When `session.regulatory_context` is non-empty and `session.documents_indexed` is empty and the gate has not been waived (not in `session.ac_waived`), the gate blocks the Phase 3 → Phase 4 transition. `TransitionEngine.attempt()` checks all open hard gates before allowing the transition. AC-S3 surfaces this as a hard gate criterion with the exact resolution prompt.

The only outstanding item is runtime integration: this gate will work correctly once the session mutation loop (Criterion 1 gap) is complete and `regulatory_context` is actually being written from user input.

---

## Criterion 5 — REVISIT Requests Without Data Loss

**Status: NOT STARTED.**

**What exists:**
- `SessionPhase.valid_transitions()` only allows forward transitions (ProblemIntake → StakeholderDiscovery → RequirementElicitation …). No backward paths are defined.
- All session data is stored in non-destructive fields (Vec, Option) so a REVISIT would not inherently lose data — but no code re-enters a prior phase.
- `IntentClassifierNode` lists a `REVISIT` intent in comments but no handling path exists.

**What is needed to close this criterion:**

This requires changes across multiple layers:

**Rust state machine:**
- Add `is_revisit: bool` and `revisit_target: Option<SessionPhase>` to `SessionState`
- Add a `revisit()` method to `TransitionEngine` that sets the current phase backward to the target without clearing any existing data (no field resets)
- Optionally add a `revisit_history: Vec<(SessionPhase, DateTime)>` audit trail

**Python pipeline:**
- When `IntentClassifierNode` returns `REVISIT` intent, extract target phase from the user message
- Route to a `RevisitHandlerNode` (new node) that calls `TransitionEngine.revisit()` and then re-enters the gap analyzer for the target phase
- Ensure the guidance generator opens with "We are back at [Phase Name]. Here is what we have so far:" and then asks the highest-priority open question for that phase

**Tests needed:**
- A session at Phase 3 can REVISIT Phase 1; the Phase 1 problem_statement field is unchanged after revisit
- A session at Phase 3 can REVISIT Phase 2; actors list is unchanged; gap analysis re-runs from Phase 2 AC
- After revisit and re-confirmation, forward progression resumes correctly

---

## Summary of What Must Be Built

The table below groups remaining work by engineering layer.

| Layer | Work Item | Criteria Unlocked |
|---|---|---|
| Rust state machine | `SessionState` mutation from `AcUpdate` inputs | 1, 4 |
| Rust state machine | Backward phase transitions for REVISIT | 5 |
| gRPC service | Wire executor to service handlers | 1, 2, 3 |
| Python — nodes | `IntentClassifierNode` LLM call (Haiku) | 1, 2 |
| Python — nodes | `EntityExtractorNode` LLM call (Haiku) | 1, 3 |
| Python — nodes | `GapAnalyzerNode` LLM call (Sonnet) | 1, 2 |
| Python — nodes | `GuidanceGeneratorNode` streaming (Sonnet/Opus) | 2 |
| Python — nodes | `RevisitHandlerNode` (new) | 5 |
| Python — prompts | Single-question constraint in guidance system prompt | 2 |
| Ingestion | Upload endpoint → chunking → Voyage embed → pgvector insert | 3 |
| Ingestion | `RAGRetrievalNode` full implementation | 3 |
| Ingestion | Provenance write on entity extraction | 3 |
| Database | Migration files for PostgreSQL + pgvector schema | 3, 4 |
| Tests | Pipeline integration test: single question per turn | 2 |
| Tests | REVISIT round-trip without data loss | 5 |

---

> Chitragupt · Sprint 1 · Gap Report · May 2026 · Delete when all criteria are closed
