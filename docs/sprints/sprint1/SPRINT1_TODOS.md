# Sprint 1 — Master Todo List

**Status:** IN PROGRESS  
**Ref:** [Sprint 1 README](README.md) · [Gap Report](SPRINT1_GAP_REPORT.md)  
**Closure rule:** All items marked ✅ and all exit criteria verified by a passing CI run before Sprint 2 begins.

Todos are ordered by dependency. Items in a block can be worked in parallel; blocks are sequential.

---

## Block A — System Prompts (no code dependencies; start here)

These are pure text files. Write them first so every node implementation has a prompt to call against.

| # | Todo | File | Done when |
|---|---|---|---|
| A-01 | Write intent classification system prompt | `services/ai-orchestration/src/ai_orchestration/prompts/intent_classifier.txt` | Covers all 8 intent codes, returns valid JSON `{"intent": "<code>"}`, handles ambiguous turns via `Clarification` default |
| A-02 | Write entity extraction system prompt | `services/ai-orchestration/src/ai_orchestration/prompts/entity_extractor.txt` | Phase-scoped (7 phase variants), returns JSON array of `{entity_type, value, confidence, source}`, includes negative examples |
| A-03 | Write gap analysis system prompt | `services/ai-orchestration/src/ai_orchestration/prompts/gap_analyzer.txt` | Takes AC list + session snapshot, returns single highest-priority gap as `{criterion_id, description, suggested_question}` |
| A-04 | Write guidance generation system prompt | `services/ai-orchestration/src/ai_orchestration/prompts/guidance_generator.txt` | Hard constraint: exactly one question OR one transition offer — never both, never zero. Separate variants for BRD phase vs all other phases. |
| A-05 | Write REVISIT re-entry prompt | `services/ai-orchestration/src/ai_orchestration/prompts/revisit_handler.txt` | Opens with phase summary, acknowledges preserved data, asks highest-priority open question for re-entered phase |

---

## Block B — Database Schema (no code dependencies; start here)

| # | Todo | File | Done when |
|---|---|---|---|
| B-01 | Write PostgreSQL migration for core session tables | `services/db/migrations/001_session_tables.sql` | Creates `sessions`, `phases`, `entities`, `ac_status` tables with RLS policies per `workspace_id` |
| B-02 | Write pgvector migration for chunk table | `services/db/migrations/002_chunk_table.sql` | Creates `document_chunks` table with `embedding vector(1024)`, BM25 index, mandatory `tenant_id`/`project_id`/`is_active` columns and ANN index |
| B-03 | Write Redis key schema document | `services/db/REDIS_SCHEMA.md` | Defines key patterns for budget tracking (`budget:{session_id}`), session cache (`session:{session_id}`), and TTL policy |

---

## Block C — Rust: SessionState Mutation (depends on B-01)

The state machine can only advance once Python can write back to it. This is the critical path for Exit Criterion 1.

| # | Todo | File | Done when |
|---|---|---|---|
| C-01 | Implement `apply_ac_update()` on `SessionState` | `services/state-machine/src/state/session.rs` | Accepts `AcUpdate {criterion_id, met, evidence}` and sets the corresponding field on `SessionState`; unit tested for all AC criterion IDs |
| C-02 | Implement `apply_entity()` on `SessionState` | `services/state-machine/src/state/session.rs` | Routes extracted entity to the correct `Vec` field (actors, requirements, constraints, assumptions) based on `entity_type`; duplicate-safe |
| C-03 | Add `revisit_target` and `revisit_history` fields to `SessionState` | `services/state-machine/src/state/session.rs` | Fields compile and serialize; default to `None` / empty Vec |
| C-04 | Implement backward phase transitions in `TransitionEngine` | `services/state-machine/src/state/transition.rs` | `revisit(target_phase)` sets current phase to target without clearing any Vec fields; records entry in `revisit_history`; rejects revisit to SignedOff |
| C-05 | Add unit tests for mutation and revisit | `services/state-machine/tests/mutation_tests.rs` | Tests: `apply_entity` appends correctly, `apply_ac_update` flips criterion, `revisit` preserves all prior data, double-revisit is idempotent |

---

## Block D — Python Nodes: Core LLM Calls (depends on A-01 → A-04)

| # | Todo | File | Done when |
|---|---|---|---|
| D-01 | Implement `IntentClassifierNode._classify()` | `services/ai-orchestration/src/ai_orchestration/agents/intent_classifier.py` | Calls Haiku with prompt A-01; parses JSON response; falls back to `Clarification` on any parse error; respects 800 ms timeout |
| D-02 | Implement `EntityExtractorNode._extract()` | `services/ai-orchestration/src/ai_orchestration/agents/entity_extractor.py` | Calls Haiku with phase-scoped prompt A-02; returns typed `list[Entity]` with `source_chunk_ids` populated when chunks are available; also emits `AcUpdate` list |
| D-03 | Implement `GapAnalyzerNode._analyze()` | `services/ai-orchestration/src/ai_orchestction/agents/gap_analyzer.py` | Calls Sonnet with prompt A-03 + current AC state from `session_state.ac_unmet`; returns single `GapResult`; falls back to deterministic first-unmet AC on timeout |
| D-04 | Implement `GuidanceGeneratorNode._generate()` | `services/ai-orchestration/src/ai_orchestration/agents/guidance_generator.py` | Streams from Sonnet (or Opus for ReviewAndSignOff) using prompt A-04; places tokens on `token_sink`; sends `None` sentinel when done; sets `pipeline_aborted=True` on unrecoverable failure |
| D-05 | Add `RevisitHandlerNode` | `services/ai-orchestration/src/ai_orchestration/agents/revisit_handler.py` | Triggered when `intent == "REVISIT"`; extracts target phase from message; calls Rust `revisit()`; re-runs gap analysis for target phase; uses prompt A-05 |

---

## Block E — RAG and Document Ingestion (depends on B-02)

| # | Todo | File | Done when |
|---|---|---|---|
| E-01 | Implement document ingestion pipeline | `services/ai-orchestration/src/ai_orchestration/ingestion/ingest.py` | Accepts file bytes + metadata; chunks to 512-token segments with 64-token overlap; embeds each chunk with `voyage-large-2`; inserts into pgvector with `tenant_id`, `project_id`, `document_id`, `page_number`, `section_title`, `is_active=true` |
| E-02 | Implement document upload endpoint | `services/api/routes/upload.py` | gRPC or HTTP POST accepting file + `{session_id, document_type}`; validates file type; calls ingest pipeline; updates `session.documents_indexed`; returns `document_id` |
| E-03 | Implement `RAGRetrievalNode._retrieve()` | `services/ai-orchestration/src/ai_orchestration/agents/rag_retrieval.py` | Voyage-embeds query; runs pgvector ANN with tenant/project/active filters; runs BM25 on same candidate set; merges with weights from config (0.7 dense / 0.3 sparse); reranks to `top_k=10`; returns `list[ChunkRef]` |
| E-04 | Implement provenance write in EntityExtractor | `services/ai-orchestration/src/ai_orchestration/agents/entity_extractor.py` | When entity is sourced from a chunk, populate `entity.source_chunk_ids` with the chunk UUIDs; persist to `entities` table with provenance |
| E-05 | Implement Redis budget accumulation | `services/ai-orchestration/src/ai_orchestration/llm/budget.py` | Replace in-process counter with `INCRBYFLOAT` on `budget:{session_id}`; `stage()` reads from Redis; TTL set to session lifetime |

---

## Block F — gRPC Service Layer (depends on C and D)

| # | Todo | File | Done when |
|---|---|---|---|
| F-01 | Define protobuf contracts | `services/api/proto/chitragupt.proto` | Defines `SendMessage`, `UploadDocument`, `GetSessionState` RPCs; streaming response for `SendMessage` |
| F-02 | Implement gRPC servicer | `services/api/servicer.py` | Wires `SendMessage` → `PipelineExecutor.run()` → token stream; applies returned `ac_updates` and `entities` to Rust `SessionState` via C-01/C-02; handles `PipelineAbortedError` gracefully |
| F-03 | Implement `GetSessionState` RPC | `services/api/servicer.py` | Returns serialised `SessionState` for the given session ID; reads from PostgreSQL; used by tests and future UI |

---

## Block G — Testing (depends on D, E, F)

All tests must pass in CI (Docker) before sprint closes.

| # | Todo | File | Done when |
|---|---|---|---|
| G-01 | Unit tests — IntentClassifierNode | `services/ai-orchestration/tests/test_intent_classifier.py` | Mocked Haiku: all 8 intents classified correctly; malformed JSON → `Clarification`; timeout → `Clarification` |
| G-02 | Unit tests — EntityExtractorNode | `services/ai-orchestration/tests/test_entity_extractor.py` | Mocked Haiku: actor extracted in Phase 2; requirement extracted in Phase 3; chunk-sourced entity has non-empty `source_chunk_ids`; empty response → empty list |
| G-03 | Unit tests — GapAnalyzerNode | `services/ai-orchestration/tests/test_gap_analyzer.py` | Mocked Sonnet: unmet AC → non-terminal gap with question; all AC met → `is_terminal=True`; timeout → deterministic fallback gap; fallback gap has non-empty `suggested_question` |
| G-04 | Unit tests — GuidanceGeneratorNode | `services/ai-orchestration/tests/test_guidance_generator.py` | Streamed tokens land on `token_sink`; `None` sentinel always sent last; non-BRD phase uses Sonnet feature; BRD phase uses Opus feature; unrecoverable error → `pipeline_aborted=True` |
| G-05 | Unit tests — RAGRetrievalNode | `services/ai-orchestration/tests/test_rag_retrieval.py` | Mocked pgvector + BM25: returns ranked `ChunkRef` list; tenant filter applied; empty result → empty list; timeout → empty list |
| G-06 | Integration test — single question invariant | `services/ai-orchestration/tests/integration/test_single_question.py` | Runs full pipeline 10 turns across 3 phases; asserts every `TurnResult` has exactly one non-empty `suggested_question` XOR `is_terminal=True`; never both, never neither |
| G-07 | Integration test — regulated domain gate | `services/ai-orchestration/tests/integration/test_regulated_gate.py` | Session with `regulatory_context` set; attempt Phase 3→4 with empty `documents_indexed` → blocked; upload a document; attempt again → allowed; explicit waiver also allows transition |
| G-08 | Integration test — REVISIT round-trip | `services/ai-orchestration/tests/integration/test_revisit.py` | Session at Phase 3; sends REVISIT message targeting Phase 1; asserts phase == ProblemIntake; asserts all Phase 3 requirements still in `session_state.requirements`; re-confirms and resumes to Phase 3 |
| G-09 | End-to-end test — full 4-phase journey | `services/ai-orchestration/tests/integration/test_e2e_journey.py` | Scripted BA conversation covering Phase 1→4; no manual state calls; each phase closes via AC satisfaction; Phase 2 org chart upload is indexed and retrieved; regulated domain path requires document; output is confirmed requirements list |
| G-10 | Rust mutation unit tests | `services/state-machine/tests/mutation_tests.rs` | See C-05 above — listed here for CI completeness tracking |

---

## Sprint 1 Exit Criteria — Closure Checklist

Mark each line when verified by a passing CI run or explicit code review.

```
[ ] 1. A new BA session can move from Problem Intake all the way to a confirmed
       requirements list through conversation alone — no manual state
       manipulation required.
       → Verified by: G-09 (e2e journey test) passing in CI

[ ] 2. The system surfaces exactly one next question or transition offer at the
       end of every turn, without exception.
       → Verified by: G-06 (single question invariant test) passing in CI

[ ] 3. A document uploaded at Checkpoint B is indexed and retrievable within
       the same session, and requirements sourced from it carry traceable
       provenance.
       → Verified by: G-09 (upload step in e2e test) + E-04 provenance write
         + manual inspection of TurnResult.entities[*].source_chunk_ids

[ ] 4. A session in a regulated domain cannot close Phase 3 without at least
       one uploaded document or an explicit BA waiver.
       → Verified by: G-07 (regulated gate integration test) passing in CI
         (gate is already implemented in Rust — test confirms it is live
         end-to-end through gRPC)

[ ] 5. The system correctly handles REVISIT requests — re-entering a prior
       phase without losing any captured data.
       → Verified by: G-08 (REVISIT round-trip test) passing in CI
```

Sprint 1 is closed when **all five boxes are checked** and the CI run is green.

---

## Dependency Order (quick reference)

```
A (prompts)  ─┐
B (schema)   ─┤
              ├─► C (Rust mutation) ─► F (gRPC) ─► G (tests)
              └─► D (Python nodes) ─┘
                  E (RAG/ingestion) ─► F (gRPC) ─► G (tests)
```

Work A and B first — they unblock everything. Work C and D in parallel. Work E in parallel with C and D. Wire F when C and D are both done. Run G continuously and fix failures before moving to Sprint 2.

---

> Chitragupt · Sprint 1 · Master Todo List · May 2026
