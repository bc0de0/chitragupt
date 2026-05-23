# Sprint 1 — Expanded Test Plan

**Status:** PLANNING  
**Ref:** [Sprint 1 README](README.md) · [Master Todo](SPRINT1_TODOS.md)  
**Owner:** Engineering  
**Last updated:** 2026-05-23

---

## 1. Philosophy

Every test in this plan answers one of three questions:

1. **Correctness** — Does the code do what the spec says?
2. **Safety** — Does a wrong input or service failure leave the system in a bad state?
3. **Quality** — Does the output actually serve the BA well?

Tests are organized into nine domains. Each domain has a coverage target across three layers:

| Layer | Scope | Tools |
|---|---|---|
| **Unit** | Single function / node in isolation; all external I/O mocked | `pytest`, `cargo test` |
| **Integration** | Two or more real services communicating over the wire | `pytest` + Docker Compose |
| **E2E** | Full BA journey from HTTP POST to final SSE complete event | `pytest` + full stack |

---

## 2. Nine Testing Domains

### Domain 1 — LLM Determinism

**Goal:** Prove that identical inputs always produce the same structured output regardless of when the test runs. This is achievable because all LLM calls use `temperature=0` and the post-processing (JSON parse, entity mapping, fallback logic) is deterministic pure code.

**Strategy:** Determinism is tested at two levels:
- **Prompt construction** — unit tests assert the exact string passed to the LLM for a given state.
- **Response parsing** — unit tests replay a fixed LLM response and assert a fixed structured output.

Real API calls are used only in integration/e2e tests where `temperature=0` is asserted in the request; we never assert the exact text string from a live call.

| ID | Description | Layer | File |
|---|---|---|---|
| T-DET-01 | IntentClassifier sends `temperature=0` in every request | Unit | `tests/unit/test_intent_classifier.py` |
| T-DET-02 | Same utterance → same intent code across 3 replayed responses | Unit | `tests/unit/test_intent_classifier.py` |
| T-DET-03 | EntityExtractor prompt is byte-for-byte identical for identical (state, message) | Unit | `tests/unit/test_entity_extractor.py` |
| T-DET-04 | GapAnalyzer selects the same gap criterion for identical AC state (deterministic sort) | Unit | `tests/unit/test_gap_analyzer.py` |
| T-DET-05 | GuidanceGenerator sends `temperature=0`; streaming chunks deterministically reassembled | Unit | `tests/unit/test_guidance_generator.py` |
| T-DET-06 | Full pipeline run twice with mocked LLM: TurnResult fields are identical | Integration | `tests/integration/test_pipeline_determinism.py` |

---

### Domain 2 — Edge Cases

**Goal:** The system must degrade gracefully for all inputs outside the happy path. No panics, no data corruption, no silent failures.

| ID | Description | Layer | File |
|---|---|---|---|
| T-EDGE-01 | Empty user message (`""`) → `Clarification` intent, pipeline completes | Unit | `tests/unit/test_intent_classifier.py` |
| T-EDGE-02 | User message > 100 000 chars → truncated to context limit, pipeline completes | Unit | `tests/unit/test_pipeline_executor.py` |
| T-EDGE-03 | LLM returns malformed JSON → intent falls back to `Clarification` | Unit | `tests/unit/test_intent_classifier.py` |
| T-EDGE-04 | LLM call times out → fallback intent + deterministic gap | Unit | `tests/unit/test_intent_classifier.py` |
| T-EDGE-05 | LLM returns empty string → entity list is empty, no crash | Unit | `tests/unit/test_entity_extractor.py` |
| T-EDGE-06 | Binary (non-text) file uploaded → rejected with `UNSUPPORTED_TYPE` status | Unit | `tests/unit/test_document_processor.py` |
| T-EDGE-07 | Zero-byte file uploaded → rejected with `EMPTY_FILE` status | Unit | `tests/unit/test_document_processor.py` |
| T-EDGE-08 | PDF with no extractable text (image-only) → `pages=[]`, status `NO_TEXT`, no crash | Unit | `tests/unit/test_document_processor.py` |
| T-EDGE-09 | Same document uploaded twice → second call returns existing `document_id` (hash dedup) | Integration | `tests/integration/test_ingestion.py` |
| T-EDGE-10 | REVISIT message with no recognisable target phase → returns `Clarification` | Unit | `tests/unit/test_revisit_handler.py` |
| T-EDGE-11 | REVISIT to the current phase → no-op, `current_phase` unchanged | Integration | `tests/integration/test_revisit.py` |
| T-EDGE-12 | Concurrent document upload + turn in same session → no race; both complete | Integration | `tests/integration/test_concurrency.py` |
| T-EDGE-13 | Session ID that does not exist → Go gateway returns 404 JSON | Integration | `tests/integration/test_gateway_errors.py` |
| T-EDGE-14 | Rust gRPC unreachable → Go gateway returns 503 within 6 s | Integration | `tests/integration/test_gateway_errors.py` |
| T-EDGE-15 | Python gRPC unreachable → Go gateway returns 503 within 6 s | Integration | `tests/integration/test_gateway_errors.py` |

---

### Domain 3 — Quality of Response

**Goal:** The text the BA sees must be actionable, grammatically valid, and free of leaked PII or internal artefacts.

Quality thresholds are based on a labelled golden dataset of 50 BA utterances (stored at `tests/fixtures/golden_utterances.jsonl`). Precision and F1 targets are conservative (early sprint); they will be raised in Sprint 2.

| ID | Description | Threshold | Layer | File |
|---|---|---|---|---|
| T-QUAL-01 | Intent classification on 50 golden utterances — precision ≥ 0.90 | p ≥ 0.90 | Integration (real LLM) | `tests/integration/test_quality.py` |
| T-QUAL-02 | Entity extraction F1 on 10 annotated transcripts | F1 ≥ 0.80 | Integration (real LLM) | `tests/integration/test_quality.py` |
| T-QUAL-03 | Guidance text contains exactly one question mark | 100% | Unit | `tests/unit/test_guidance_generator.py` |
| T-QUAL-04 | Guidance text does not mention internal field names (`ac_met`, `session_id`, etc.) | 100% | Unit | `tests/unit/test_guidance_generator.py` |
| T-QUAL-05 | Gap suggested_question is non-empty and ≥ 10 chars for any unmet AC | 100% | Unit | `tests/unit/test_gap_analyzer.py` |
| T-QUAL-06 | PII scrubber removes email, phone, SSN, credit card from chunk text before embedding | 100% | Unit | `tests/unit/test_ingestion_pipeline.py` |
| T-QUAL-07 | Retrieved chunks have cosine similarity ≥ 0.65 to query embedding (spot check 5 queries) | ≥ 0.65 | Integration | `tests/integration/test_rag_quality.py` |
| T-QUAL-08 | No chunk from workspace A is returned for a query in workspace B | 100% | Integration | `tests/integration/test_rag_quality.py` |

---

### Domain 4 — State Boundary Conditions & Gating Logic

**Goal:** Every guard in the state machine must be tested at the boundary — one AC short of passing, exactly at the threshold, and with optional vs required distinctions.

These tests exercise the Rust state machine directly via gRPC (no Python involvement) to isolate state logic from LLM variability.

| ID | Description | Layer | File |
|---|---|---|---|
| T-STATE-01 | Fresh session: all ACs unmet, transition_ready = false for all phases | Unit (Rust) | `services/state-machine/tests/ac_evaluators.rs` |
| T-STATE-02 | Optional AC (`-U` suffix) unmet → appears in gaps list, does NOT block transition_ready | Unit (Rust) | `services/state-machine/tests/ac_evaluators.rs` |
| T-STATE-03 | All required ACs met, optional AC unmet → transition_ready = true | Unit (Rust) | `services/state-machine/tests/ac_evaluators.rs` |
| T-STATE-04 | AC waived → removed from gaps, not from unmet count | Unit (Rust) | `services/state-machine/tests/mutation_tests.rs` |
| T-STATE-05 | All Phase 1 required ACs met → RequestTransition to Phase 2 approved | Integration | `tests/integration/test_state_boundaries.py` |
| T-STATE-06 | One required AC short in Phase 1 → RequestTransition rejected | Integration | `tests/integration/test_state_boundaries.py` |
| T-STATE-07 | Phase 3 regulated domain, documents_indexed empty → Phase 3→4 blocked | Integration | `tests/integration/test_regulated_gate.py` |
| T-STATE-08 | Phase 3 regulated domain, one document indexed → Phase 3→4 allowed | Integration | `tests/integration/test_regulated_gate.py` |
| T-STATE-09 | Phase 3 regulated domain, AC-S3-U1 waived → Phase 3→4 allowed | Integration | `tests/integration/test_regulated_gate.py` |
| T-STATE-10 | REVISIT Phase 4 → Phase 2: phase changes, all Phase 4 entities preserved | Integration | `tests/integration/test_revisit.py` |
| T-STATE-11 | REVISIT to SignedOff rejected with error | Integration | `tests/integration/test_revisit.py` |
| T-STATE-12 | Forward transition from SignedOff rejected | Integration | `tests/integration/test_state_boundaries.py` |
| T-STATE-13 | Double transition (same target twice) → second returns current_phase unchanged | Integration | `tests/integration/test_state_boundaries.py` |
| T-STATE-14 | apply_entity with duplicate entity → deduplicated in the Vec | Unit (Rust) | `services/state-machine/tests/mutation_tests.rs` |
| T-STATE-15 | apply_ac_update for unknown criterion_id → rejected with error | Unit (Rust) | `services/state-machine/tests/mutation_tests.rs` |

---

### Domain 5 — Code Correctness

**Goal:** All non-LLM logic (parsers, chunkers, embedders, serializers, converters) is deterministic and must pass exact-value unit tests.

| ID | Description | Layer | File |
|---|---|---|---|
| T-CORR-01 | Chunker: 512-token window produces correct chunk boundaries | Unit | `tests/unit/test_chunker.py` |
| T-CORR-02 | Chunker: 64-token overlap — last 64 tokens of chunk N = first 64 tokens of chunk N+1 | Unit | `tests/unit/test_chunker.py` |
| T-CORR-03 | Chunker: chunks shorter than min_tokens (50) are discarded | Unit | `tests/unit/test_chunker.py` |
| T-CORR-04 | BM25 sparse vector: TF-IDF weights sum to ≤ 1.0, empty input → empty dict | Unit | `tests/unit/test_ingestion_pipeline.py` |
| T-CORR-05 | PII scrubber: valid email removed; valid phone (E.164) removed; SSN removed; CC removed | Unit | `tests/unit/test_ingestion_pipeline.py` |
| T-CORR-06 | PII scrubber: non-PII strings pass through unchanged | Unit | `tests/unit/test_ingestion_pipeline.py` |
| T-CORR-07 | DocumentProcessor: PDF extraction returns `RawPage` list with correct page numbers | Unit | `tests/unit/test_document_processor.py` |
| T-CORR-08 | DocumentProcessor: DOCX extraction returns paragraphs with section metadata | Unit | `tests/unit/test_document_processor.py` |
| T-CORR-09 | Proto roundtrip: `SessionStateProto` serialised → bytes → deserialised → identical fields | Unit (Go) | `services/api-gateway/internal/gateway/handler_test.go` |
| T-CORR-10 | `state_json` roundtrip: Rust `SessionState` → JSON → Python dict parse → same field values | Integration | `tests/integration/test_state_json.py` |
| T-CORR-11 | Rust `apply_ac_update`: every criterion ID in every phase routes to correct field | Unit (Rust) | `services/state-machine/tests/mutation_tests.rs` |
| T-CORR-12 | Rust `apply_entity`: all four entity_type values append to correct Vec | Unit (Rust) | `services/state-machine/tests/mutation_tests.rs` |
| T-CORR-13 | Rust `revisit`: revisit_history entry has correct target phase + timestamp | Unit (Rust) | `services/state-machine/tests/mutation_tests.rs` |
| T-CORR-14 | BudgetTracker key format: `budget:{workspace_id}:{session_id}:total_usd` | Unit | `tests/unit/test_budget.py` |
| T-CORR-15 | `sessionStateJSON` Go helper: all required fields present in output map | Unit (Go) | `services/api-gateway/internal/gateway/handler_test.go` |

---

### Domain 6 — Code Integration Tests

**Goal:** Every service boundary is exercised with real services (no mocks) running in Docker Compose. These tests catch serialisation mismatches, gRPC contract drift, and connection-handling bugs that unit tests cannot detect.

| ID | Description | Layer | File |
|---|---|---|---|
| T-INT-01 | Go → Rust: `CreateSession` then `GetSessionState` returns matching session_id | Integration | `tests/integration/test_grpc_state.py` |
| T-INT-02 | Go → Rust: `ApplyTurnResult` with one entity → `GetSessionState` shows entity | Integration | `tests/integration/test_grpc_state.py` |
| T-INT-03 | Go → Rust: `ApplyTurnResult` with one AcUpdate → unmet_ac_count decreases | Integration | `tests/integration/test_grpc_state.py` |
| T-INT-04 | Go → Rust: `RequestTransition` with all ACs met → approved | Integration | `tests/integration/test_grpc_state.py` |
| T-INT-05 | Go → Rust: `RevisitPhase` to prior phase → ok, current_phase updated | Integration | `tests/integration/test_grpc_state.py` |
| T-INT-06 | Go → Python: `RunPipeline` streams ≥ 1 token event before complete event | Integration | `tests/integration/test_grpc_orchestration.py` |
| T-INT-07 | Go → Python: `IngestDocument` returns accepted status; background task fires | Integration | `tests/integration/test_grpc_orchestration.py` |
| T-INT-08 | Python → asyncpg: inserted chunks retrievable by `hybrid_search` within same session | Integration | `tests/integration/test_ingestion.py` |
| T-INT-09 | Python → asyncpg: RLS enforced — session A cannot retrieve session B chunks | Integration | `tests/integration/test_ingestion.py` |
| T-INT-10 | Python → Redis: `BudgetTracker.record()` increments key; TTL is 7 days | Integration | `tests/integration/test_budget_integration.py` |
| T-INT-11 | Full gRPC stack: Go HTTP POST → Rust state → Python pipeline → Go SSE complete | Integration | `tests/integration/test_full_stack.py` |
| T-INT-12 | Go gateway `/healthz` returns 200 when both gRPC backends are up | Integration | `tests/integration/test_gateway_health.py` |

---

### Domain 7 — Latency

**Goal:** Every critical path has a latency budget. Latency tests run against the full Docker Compose stack with warm connections. Tests fail if the p95 of N=10 trials exceeds the threshold.

| ID | Description | Budget | Trials | Layer | File |
|---|---|---|---|---|---|
| T-LAT-01 | IntentClassifier response time (real Haiku, temperature=0) | p95 ≤ 800 ms | 10 | Integration | `tests/integration/test_latency.py` |
| T-LAT-02 | Full pipeline first-token latency (no RAG, no documents) | p95 ≤ 3 000 ms | 10 | Integration | `tests/integration/test_latency.py` |
| T-LAT-03 | Full pipeline first-token latency (RAG enabled, 1 000 chunks indexed) | p95 ≤ 4 500 ms | 10 | Integration | `tests/integration/test_latency.py` |
| T-LAT-04 | RAG hybrid_search with 100 000 chunks in DB | p95 ≤ 500 ms | 10 | Integration | `tests/integration/test_latency.py` |
| T-LAT-05 | Rust gRPC `ApplyTurnResult` round-trip (Go → Rust → Go) | p95 ≤ 10 ms | 50 | Integration | `tests/integration/test_latency.py` |
| T-LAT-06 | Go gateway SSE: time from POST to first `event: token` | p95 ≤ 5 000 ms | 10 | E2E | `tests/e2e/test_latency_e2e.py` |
| T-LAT-07 | Document ingestion pipeline: 5 MB PDF fully indexed | p95 ≤ 60 s | 5 | Integration | `tests/integration/test_latency.py` |
| T-LAT-08 | Streaming throughput: sustained token rate after first token | ≥ 10 tok/s | 5 | E2E | `tests/e2e/test_latency_e2e.py` |

---

### Domain 8 — Context Awareness

**Goal:** The pipeline must be aware of the current BA session state at every step — the right phase prompt, the right tenant's chunks, continuity across turns.

| ID | Description | Layer | File |
|---|---|---|---|
| T-CTX-01 | EntityExtractor uses Phase 2 system prompt variant when phase = StakeholderDiscovery | Unit | `tests/unit/test_entity_extractor.py` |
| T-CTX-02 | EntityExtractor uses Phase 3 system prompt variant when phase = RequirementElicitation | Unit | `tests/unit/test_entity_extractor.py` |
| T-CTX-03 | Retrieved chunks are scoped to current session's workspace_id + project_id | Integration | `tests/integration/test_rag_quality.py` |
| T-CTX-04 | Entity captured in Turn N is present in the context dict passed to Turn N+1 | Integration | `tests/integration/test_context_continuity.py` |
| T-CTX-05 | REVISIT re-entry: gap analysis uses updated AC state, not stale pre-revisit cache | Integration | `tests/integration/test_revisit.py` |
| T-CTX-06 | 50-turn session: no `context_length_exceeded` error; pipeline completes every turn | Integration | `tests/integration/test_context_continuity.py` |
| T-CTX-07 | Chunk indexed in Turn 1 is retrieved in Turn 10 (TTL and active flag intact) | Integration | `tests/integration/test_context_continuity.py` |
| T-CTX-08 | GuidanceGenerator prompt includes the most recent gap criterion ID and description | Unit | `tests/unit/test_guidance_generator.py` |

---

### Domain 9 — Budget & Commercial

**Goal:** Every dollar spent on LLM / embedding calls is tracked, reported, and survives Redis failure without breaking the pipeline.

| ID | Description | Layer | File |
|---|---|---|---|
| T-BUD-01 | IntentClassifier cost (input + output tokens × Haiku rate) recorded in Redis after turn | Integration | `tests/integration/test_budget_integration.py` |
| T-BUD-02 | Costs from 5 turns accumulate correctly via `INCRBYFLOAT` (sum matches sum of individual) | Integration | `tests/integration/test_budget_integration.py` |
| T-BUD-03 | Budget Redis key TTL is exactly 7 days after last write | Integration | `tests/integration/test_budget_integration.py` |
| T-BUD-04 | Redis unavailable → pipeline completes; cost is recorded 0.0 in TurnComplete | Integration | `tests/integration/test_budget_integration.py` |
| T-BUD-05 | `cost_usd` in SSE complete event matches sum of all LLM calls in that turn | Integration | `tests/integration/test_budget_integration.py` |
| T-BUD-06 | `total_cost_usd` in `SessionStateProto` accumulates across `ApplyTurnResult` calls | Integration | `tests/integration/test_grpc_state.py` |
| T-BUD-07 | Session with 200 turns (simulated, mocked LLM) — no float overflow, precision ≤ 0.001 USD | Unit | `tests/unit/test_budget.py` |
| T-BUD-08 | BudgetTracker `load()` returns last recorded value on subsequent call | Unit | `tests/unit/test_budget.py` |
| T-BUD-09 | Voyage embedding cost (token count × rate) tracked and included in turn total | Unit | `tests/unit/test_budget.py` |

---

## 3. E2E Test Suites

The following E2E suites exercise the entire stack (HTTP → Go → Rust/Python → SSE) with no mocks. They depend on all integration tests passing.

| ID | Description | File |
|---|---|---|
| T-E2E-01 | Full 4-phase journey (Phase 1→4) via conversation alone | `tests/e2e/test_journey_4phase.py` |
| T-E2E-02 | Single-question invariant: every turn in 10-turn session has exactly one question XOR terminal | `tests/e2e/test_single_question_invariant.py` |
| T-E2E-03 | Regulated domain path: document required before Phase 3→4 transition | `tests/e2e/test_regulated_gate_e2e.py` |
| T-E2E-04 | REVISIT round-trip: Phase 4 → revisit Phase 2 → resume to Phase 4 | `tests/e2e/test_revisit_e2e.py` |
| T-E2E-05 | Document provenance: entity extracted from uploaded doc carries source chunk IDs | `tests/e2e/test_provenance_e2e.py` |

---

## 4. Test Infrastructure

### Fixtures and Shared Helpers

| Path | Purpose |
|---|---|
| `tests/fixtures/golden_utterances.jsonl` | 50 labelled BA utterances with expected intent and entity annotations |
| `tests/fixtures/sample_documents/` | PDF (with text), DOCX, TXT, image-only PDF, zero-byte file for processor tests |
| `tests/fixtures/session_states/` | JSON snapshots of `SessionState` at each phase boundary for state boundary tests |
| `tests/conftest.py` | `pytest` fixtures: asyncpg pool, Redis client, gRPC stubs, Docker Compose lifecycle |
| `tests/helpers/sse_client.py` | SSE stream reader for E2E tests — collects `token` and `complete` events |
| `tests/helpers/grpc_helpers.py` | Pre-built gRPC channels + stub factories for each service |

### Docker Compose Test Profile

```
docker compose --profile test up
```

Services in the `test` profile:

- `postgres-test` — fresh DB, migrations applied via `tests/conftest.py` on startup
- `redis-test` — standalone, no persistence
- `state-machine-test` — Rust service compiled with `--profile release`
- `orchestration-test` — Python service with `TESTING=1` (real LLM calls gated by `ENABLE_LIVE_LLM=1`)
- `api-gateway-test` — Go gateway pointing at test service addresses

Environment variables for CI:

```
ANTHROPIC_API_KEY      — required for T-QUAL-* and T-LAT-* (live LLM calls)
VOYAGE_API_KEY         — required for T-LAT-03, T-LAT-04, T-CTX-03, T-QUAL-07
DATABASE_URL           — set to postgres-test by compose
REDIS_URL              — set to redis-test by compose
ENABLE_LIVE_LLM        — set to 1 only in quality and latency test runs
```

### Test Run Modes

| Mode | Tests run | LLM calls | Secrets required |
|---|---|---|---|
| `fast` (default CI) | All unit + integration except T-QUAL, T-LAT | Mocked | None |
| `quality` | T-QUAL-* only | Real | `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY` |
| `latency` | T-LAT-* + T-E2E-08 only | Real | `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY` |
| `full` | Everything | Real | All secrets |

Run modes are selected with a `pytest` marker: `pytest -m fast`, `pytest -m quality`, etc.

---

## 5. Coverage Map

Summary of all tests by domain × layer:

| Domain | Unit | Integration | E2E | Total |
|---|---|---|---|---|
| 1 — LLM Determinism | 5 | 1 | — | 6 |
| 2 — Edge Cases | 9 | 6 | — | 15 |
| 3 — Quality | 5 | 3 | — | 8 |
| 4 — State Boundaries | 10 | 5 | — | 15 |
| 5 — Code Correctness | 15 | — | — | 15 |
| 6 — Code Integration | — | 12 | — | 12 |
| 7 — Latency | — | 6 | 2 | 8 |
| 8 — Context Awareness | 2 | 6 | — | 8 |
| 9 — Budget & Commercial | 4 | 5 | — | 9 |
| E2E Suites | — | — | 5 | 5 |
| **Total** | **50** | **44** | **7** | **101** |

---

## 6. Expanded Sprint 1 Exit Criteria

The original 5 exit criteria are retained unchanged. These 4 are added:

```
[ ] 6. LLM calls are deterministic at the parsing layer — identical mocked responses
       produce identical TurnResult outputs across 3 runs for all 4 node types.
       → Verified by: T-DET-01 through T-DET-05 green in CI (fast mode)

[ ] 7. All edge-case inputs (empty message, malformed JSON, binary file, unreachable
       gRPC backend) are handled without a 5xx error or an unrecovered panic.
       → Verified by: T-EDGE-01 through T-EDGE-15 green in CI (fast mode)

[ ] 8. Budget tracking is accurate to within 0.001 USD across 200 simulated turns,
       and the pipeline completes normally when Redis is unavailable.
       → Verified by: T-BUD-01 through T-BUD-09 green in CI (fast mode)

[ ] 9. p95 latency for first-token delivery is ≤ 5 000 ms end-to-end under normal load.
       → Verified by: T-LAT-06 green in CI (latency mode, requires API keys)
```

Sprint 1 is fully closed when **all nine boxes are checked**, with the fast-mode CI run green and the latency/quality runs recorded (not necessarily as CI gates, but as artefacts).

---

## 7. Implementation Order

Tests should be written in this order to maximise parallelism with ongoing code work:

```
Week 1 (parallel with code cleanup):
  Domain 5 (Correctness) — pure unit tests, no deps
  Domain 1 (Determinism) — pure unit tests once prompts are stable
  Domain 9 Unit (Budget) — pure unit tests

Week 2 (after Docker Compose test profile is ready):
  Domain 4 (State Boundaries) — Rust unit + gRPC integration
  Domain 2 (Edge Cases) — mix of unit and integration
  Domain 6 (Integration) — full gRPC integration suite

Week 3 (after integration suite is green):
  Domain 3 (Quality) — requires golden dataset + real LLM
  Domain 7 (Latency) — requires warm stack
  Domain 8 (Context) — requires multi-turn sessions
  E2E suites
```

---

> Chitragupt · Sprint 1 · Expanded Test Plan · May 2026
