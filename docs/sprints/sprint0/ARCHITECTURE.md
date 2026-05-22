# Architecture Principles — Chitragupt

**Version:** 4.0 — Sprint 0 Canonical
**Status:** Binding. Any system behavior that violates a rule in this document is a defect, not a product decision.

This document is the authoritative reference for how Chitragupt acquires, validates, weighs, and emits knowledge — and the non-negotiable rules that govern system behavior. It consolidates epistemology, invariants, and engineering conventions into a single source of truth.

---

## 1. Trust Hierarchy

Every claim in a generated specification must be traceable to a source with an assigned trust rank. Higher ranks always win. Silent merging across ranks is prohibited.

```mermaid
graph TB
    R1["Rank 1 — Human Override\nAbsolute authority\nBA edits · Approvals · Rejections · Conflict resolutions"]
    R2["Rank 2 — Structured External Systems\nHigh trust\nJira fields · Typed API contracts · Database schemas"]
    R3["Rank 3 — Primary Source Documents\nBaseline trust\nClient PDFs · Signed Confluence pages · Official emails"]
    R4["Rank 4 — Secondary Documents\nModerate trust\nMeeting notes · Slack threads · Internal memos"]
    R5["Rank 5 — Agentic Inference\nConditional trust\nLLM synthesis · Industry-standard assumptions"]

    R1 --> R2
    R2 --> R3
    R3 --> R4
    R4 --> R5

    style R1 fill:#0D47A1,color:#fff,stroke:#0D47A1
    style R2 fill:#1565C0,color:#fff,stroke:#1565C0
    style R3 fill:#1976D2,color:#fff,stroke:#1976D2
    style R4 fill:#42A5F5,color:#212121,stroke:#42A5F5
    style R5 fill:#90CAF9,color:#212121,stroke:#90CAF9
```

**Strict rules:**
- A Rank 5 claim may never supersede or silently replace a Rank 3+ claim.
- When two sources of different rank conflict, the higher rank wins and the lower-rank claim is discarded or flagged — never merged.
- When two sources of the **same** rank conflict, see Section 4 (Conflict Protocol).
- Every claim in the output must declare its trust rank in the `source_chunks` metadata.

---

## 2. Confidence Scoring

Every synthesized output carries a calibrated confidence score (float, 0.0–1.0) computed from five weighted signals. The score determines the output's tag and whether it may appear in the specification.

### 2.1 Score Computation

| Signal | Weight | Description |
|---|---|---|
| Retrieval score | 40% | Cosine similarity between query and retrieved chunk |
| Re-ranking score | 30% | Cross-encoder score after initial retrieval — more precise than cosine |
| Source trust tier | 15% | Higher-tier sources (Rank 2–3) receive a confidence boost |
| LLM self-reported certainty | 10% | Discounted because LLMs are known to be overconfident |
| Historical validation rate | 5% | Empirical rate at which similar past inferences were approved by humans |

### 2.2 Confidence Tiers and Output Rules

| Score | Tier | Tag in Output | Action |
|---|---|---|---|
| 0.85–1.00 | Explicit Extraction | *(no tag)* | Include as-is |
| 0.65–0.84 | Deductive Synthesis | `[SYNTHESIZED]` | Include; surfaced in review |
| 0.40–0.64 | Inductive Inference | `[INFERRED — VERIFY]` | Include; also raised as Open Question |
| < 0.40 | Speculative | — | **Do not include.** Raise as Open Question instead |

**Hard rules:**
- Confidence tags must appear in both the database record and every rendered output (chat, DOCX, PDF, Mermaid export).
- Tags may only be removed from the final locked specification once a human has explicitly approved the requirement.
- Stripping a tag before human approval is a product defect.
- Visual extractions (diagrams, screenshots, video frames) have a hard confidence cap of **0.80** regardless of computed score. They always carry `[VISUAL EXTRACTION — VERIFY]`.

### 2.3 Calibration Requirements

A score of 0.70 must correspond to approximately 70% empirical correctness as judged by domain experts.

| Metric | Target |
|---|---|
| Brier Score | < 0.15 |
| Expected Calibration Error (ECE) | < 0.10 |
| Human rejection rate for claims scored > 0.85 | < 15% |

**Recalibration trigger:** If the human rejection rate for high-confidence claims (> 0.85) exceeds 15% over any 30-day rolling window, the confidence model is miscalibrated and must be reviewed before further processing continues.

**Calibration process:**
1. Sample 100 requirements from the evaluation dataset.
2. Have 2 domain experts independently rate each as: Correct / Incorrect / Partially Correct.
3. Plot predicted confidence vs. empirical accuracy (reliability curve).
4. Re-evaluate quarterly or after any LLM model version upgrade.

---

## 3. Traceability — The Provenance Contract

For a requirement to be valid, the system must be able to prove how it knows it. Provenance is not optional metadata — it is a structural property of every knowledge object.

### 3.1 Required Provenance Fields

Every generated requirement, constraint, and assumption must carry:

| Field | Type | Description |
|---|---|---|
| `source_chunks` | UUID[] | At least one active, non-tombstoned chunk in the vector store |
| `retrieval_score` | float | Cosine similarity at retrieval time |
| `rerank_score` | float | Cross-encoder score |
| `created_by_agent` | string | Agent ID that synthesized this requirement |
| `model_id` | string | Pinned model version used (e.g., `claude-sonnet-4-6`) |
| `created_at` | timestamp | UTC timestamp of synthesis |
| `confidence_score` | float | Final calibrated score |

### 3.2 Citation Format

Human-readable citations must appear in the review UI and all export formats alongside the requirement:

```
[Source: Payment_Gateway_V2.pdf, p.4 — Confidence: 0.92]
[Source: Jira Epic ENG-1234 — Confidence: 0.87]
[INFERRED from industry standard (GDPR Art.17) — Confidence: 0.61 — REQUIRES VALIDATION]
[VISUAL EXTRACTION — Architecture_Diagram.png — Confidence: 0.74 — VERIFY]
```

### 3.3 Orphan Knowledge

Any LLM-generated claim that cannot be mapped to at least one active chunk in the vector store is **Orphan Knowledge** — treated as a hallucination until proven otherwise.

**Required handling:**
- Never include Orphan Knowledge in the specification as a confirmed requirement.
- Must be raised as an Open Question (Gap) or tagged `[SPECULATIVE — REVIEW]` if tentatively included.
- The Review Agent must actively surface all Orphan Knowledge in the review session before any specification is approved.

---

## 4. Conflict Protocol

When two sources contradict each other, the system halts on that topic. It does not guess which source is correct under any circumstances.

```mermaid
flowchart TD
    A[Two sources address the same topic] --> B{Same trust rank?}

    B -->|No — different ranks| C[Higher rank wins\nLower-rank claim discarded or flagged\nNo conflict object created]

    B -->|Yes — same rank| D[Create Conflict object\nHalt synthesis for this topic\nMark section CONFLICT PENDING RESOLUTION]

    D --> E[Surface both sources\nside-by-side in review UI\nwith full citations]

    E --> F{Human selects resolution}

    F -->|Accept Source A| G[Source A becomes Rank 1 ground truth\nSource B discarded]
    F -->|Accept Source B| H[Source B becomes Rank 1 ground truth\nSource A discarded]
    F -->|Provide Clarification| I[New human statement becomes Rank 1\nBoth original sources retained as evidence]

    G --> J[Resume synthesis\nUsing resolved ground truth]
    H --> J
    I --> J
```

### 4.1 Conflict Types

| Type | Example | System Action |
|---|---|---|
| Direct Contradiction | Source A: "Daily sync." Source B: "Real-time sync." | Conflict flag; halt synthesis |
| Scope Overlap | Feature X specified for Admin in Source A; for All Users in Source B | Conflict flag; synthesize both as candidates |
| Version Conflict | Same document exists in v1 (uploaded) and v2 (linked); they differ | Flag version discrepancy; use most recent by default; notify user |
| Implicit Contradiction | Feature implies SLA X; constraint document implies max SLA Y where X > Y | Inferred conflict; tag both; ask stakeholder to clarify |

### 4.2 Non-Negotiable Rule

An agent may not programmatically resolve a conflict between equal-rank sources. An agent may provide a recommendation (e.g., "Source B appears more recent") but the resolution action is exclusively a human action. Automated conflict resolution is a critical defect.

---

## 5. Temporal Validity

Knowledge has a temporal dimension. A fact that was true when a document was ingested may be false when that document is updated.

### 5.1 Chunk Validity Window

Every chunk carries:
- `valid_from` — timestamp of ingestion (mandatory)
- `valid_until` — timestamp of tombstoning (null while active)
- `is_active` — boolean; false for tombstoned chunks

**Rules:**
- Chunks with a non-null `valid_until` that has passed must be excluded from all retrieval queries. This filter may never be removed by a performance optimization, migration, or configuration change.
- When a document is re-ingested after an update, old chunks are tombstoned (`is_active = false`, `valid_until = NOW()`) — never hard-deleted. The traceability chain must remain queryable indefinitely.
- Requirements derived solely from tombstoned or expired chunks must be flagged for re-validation.

### 5.2 Staleness Detection

| Event | System Response |
|---|---|
| Source document updated (new upload) | Old chunks tombstoned; new chunks re-embedded; spec flagged for re-review |
| Connector source updated (Jira/Confluence webhook) | Diff-based re-embedding of changed sections only; staleness alert raised |
| Source not verified by a human in > 90 days | Requirements derived from it marked `[SOURCE MAY BE STALE — VERIFY]` |
| User marks a source as "superseded" | All chunks from that source excluded from future retrieval; linked requirements flagged |
| Spec is locked and approved | Contributing source chunks are snapshotted; subsequent changes to sources do not affect the locked spec |

The staleness threshold (default 90 days) is configurable per workspace.

---

## 6. Multi-Modal Input Handling

| Modality | Trust Level | Handling |
|---|---|---|
| Plain text (PDF / DOCX) | Baseline | Direct extraction + chunking; tables require structured parsing |
| Spreadsheet (XLSX) | High — structured | Row = potential requirement; column headers define semantic schema |
| Diagram / Image | Moderate — vision | Vision LLM extraction; confidence hard-capped at 0.80; `[VISUAL EXTRACTION — VERIFY]` mandatory |
| Audio recording | Moderate | STT transcription → text pipeline; speaker attribution affects trust level |
| Video (screen recording) | Moderate | Frame extraction + transcription; treat as secondary confirmation, not primary source |
| Chat session (elicitation) | High — recency | Authoritative for the question asked; may conflict with older documents |
| URL / Web page | Baseline | `source_type: web`; authoritativeness not verifiable; cannot be cited as a primary source |

### 6.1 Vision Extraction Protocol

1. Vision-capable LLM invoked to describe diagram entities and relationships.
2. Extracted description embedded as a chunk with `source_type: visual_extraction` and `confidence_modifier: -0.15`.
3. All vision-derived claims tagged `[VISUAL EXTRACTION — VERIFY]` regardless of score.
4. Original image stored and linkable from citation viewer so the reviewer can manually verify the extraction.

---

## 7. Epistemic Language Rules

The language model must use output language that matches the confidence tier. Using normative language (`shall`, `must`) for inferred claims is a hallucination risk and a legal liability.

| Confidence | Required Language |
|---|---|
| ≥ 0.85 — Explicit | "The system **shall**..." (mandatory, normative) |
| 0.65–0.84 — Synthesized | "Based on [source], the system **should**..." |
| 0.40–0.64 — Inferred | "It is recommended that the system considers..." + `[INFERRED — VERIFY]` tag |
| < 0.40 | Do not generate. Raise as Open Question. |

No prompt, user preference, or runtime configuration may override this rule.

---

## 8. Out-of-Knowledge Scenarios

The system must know what it does not know and say so explicitly rather than speculate.

| Scenario | Required Response |
|---|---|
| No source chunk covers the topic | Open Question: "No information found for [topic]. Please provide clarification." |
| All retrieved chunks have confidence < 0.40 | Open Question; do not include speculative claim |
| Topic requires domain expertise beyond the ingested corpus | Open Question: "This topic may require SME input." |
| Topic explicitly marked out-of-scope in a source document | Do not generate requirement; note the exclusion with citation |
| Stakeholder input contradicts itself within a single session | Raise internal conflict; ask for clarification before proceeding |

---

## 9. Feedback Loops & Knowledge Improvement

Human reviewer behavior must feed back into the system's knowledge quality over time.

| Human Action | Signal | Effect |
|---|---|---|
| Approves a requirement | Positive for: retrieval query, chunks used, synthesis approach | Used in calibration; boosts similar chunks in future retrievals |
| Rejects a requirement | Negative; captures rejection reason | Chunk receives soft negative weight for this retrieval context |
| Edits a requirement | Delta between AI text and human edit is logged | Informs prompt template refinement |
| Resolves a conflict (chooses A or B) | Resolution pattern recorded | Similar conflicts in same domain use pattern as a soft hint |
| Marks `[INFERRED]` as valid | Validates inference pattern | Raises confidence floor for similar inferences in this domain |
| Marks `[INFERRED]` as invalid | Invalidates inference | Lowers confidence for similar inferences; triggers review of related claims |

**Tenant isolation of feedback:** Feedback from Tenant A never directly modifies the knowledge base used by Tenant B. Cross-tenant learning is permitted only for aggregate calibration statistics (no identifiable data) with explicit workspace opt-in.

---

## 10. Non-Negotiable Invariants

These hold under all conditions including edge cases, failures, and high load. Violations are system bugs, not product decisions.

### Security

**INV-SEC-01 — Tenant Isolation:** No data from Tenant A may be queried, retrieved, or displayed in a Tenant B session. Enforced via separate vector namespaces, PostgreSQL RLS, JWT-bound API middleware, and mandatory `tenant_id` filter on every vector query. Any vector query issued without a `tenant_id` filter is a critical defect.

**INV-SEC-02 — PII Scrubbing:** Chat session and elicitation content must be scanned and PII-redacted before any embedding call. Scrubbing executes before embedding, never after.

**INV-SEC-03 — File Isolation:** Uploaded documents are stored at paths scoped to `{tenant_id}/{project_id}/`. No user may receive a presigned URL pointing to another tenant's file.

**INV-SEC-04 — Audit Log Immutability:** The audit log is append-only. No entry may be modified or deleted by any user, agent, or process.

### Epistemology

**INV-EPI-01 — Traceability:** Every requirement in the final specification must contain a populated `source_chunks` array pointing to at least one active chunk. Requirements with empty source arrays may not be written to the database except as explicit human overrides.

**INV-EPI-02 — Conflict Non-Resolution:** The agent may not unilaterally resolve conflicts between equal-tier sources. It must halt and raise a Conflict object.

**INV-EPI-03 — Confidence Tagging:** Any output with confidence < 0.85 must carry the appropriate confidence tag in both the database record and the rendered output. Stripping tags is a product defect.

**INV-EPI-04 — Embedding Consistency:** All chunks in a vector namespace must use the same embedding model and dimension. Mixing models within a single index is strictly prohibited. Model upgrades require full re-embedding of all active chunks before queries are issued.

### HITL Authority

**INV-HITL-01 — Human Override:** A human edit, approval, or rejection is absolute ground truth. The system may not overwrite a human edit during re-generation cycles. The original AI text is preserved in `human_override_text`; the human edit is in `description`.

**INV-HITL-02 — No Auto-Push:** No generated artifact may be pushed to downstream systems (Jira, Confluence, CI/CD) without explicit human approval of that specific export. Specifications in `draft` or `in_review` status must never trigger external writes.

**INV-HITL-05 — Spec Lock:** A locked specification is immutable. No further automated changes may be made to its requirements, constraints, or assumptions. Changes after locking require creating a new specification version.

### Cost Control

**INV-COST-01 — Project Budget Cap:** When a project's cost reaches its configured cap, all agent tasks for that project stop. The state is preserved. A human must explicitly raise the cap to resume.

**INV-COST-03 — Cost Attribution:** Every LLM call must be attributed to a specific project, agent, and model tier before it is issued. Unattributed calls are prohibited.

**INV-MODEL-03 — Pinned Model Versions:** All LLM calls must use pinned model versions (e.g., `claude-sonnet-4-6`, not `claude-sonnet-latest`). Model upgrades are treated as deployment events with quality validation.

---

## 11. Engineering Conventions

### Python Standards

- Formatter: `black` (line length 88)
- Imports: `isort` with black-compatible profile
- Type hints: mandatory on all function signatures; `mypy --strict` must pass
- No multi-paragraph docstrings — one short line max, only when the why is non-obvious

### Git Protocol

Branch naming: `feat/sprint-N-name`, `fix/id-name`, `chore/name`, `perf/name`

Commit format (Conventional Commits):
```
<type>(<scope>): <description>
```
Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

Breaking changes: append `!` after type/scope or add `BREAKING CHANGE:` footer.

### Database Protocol

- RLS enabled on every table containing tenant-specific data
- Session variable `app.current_tenant_id` set at transaction start
- No raw DB sessions — use the service wrapper that attaches tenant context automatically
- Vector similarity queries: always include tenant filter, similarity threshold ≥ 0.65, limit ≤ 15 chunks
- HNSW index (cosine ops) required once a vector table exceeds 50k active rows

### LLM Client Protocol

- Wrap every LLM call in retry with exponential backoff + jitter (max 3 retries)
- Fallback chain: primary → secondary (different vendor) → dead-letter queue
- Zero data-retention enterprise endpoints only
- System prompt placed in protected position preceding all retrieved content (prompt injection containment)
- Validate structured output against expected schema before writing to database; retry up to 3 times on schema failure

---

> Chitragupt Architecture Principles · v4.0 · Sprint 0 Canonical · May 2026
