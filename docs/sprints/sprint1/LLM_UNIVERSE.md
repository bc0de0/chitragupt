# LLM Universe — Chitragupt

**Status:** Binding for Sprint 1 implementation
**Scope:** Python AI Orchestration service (`services/ai-orchestration`)
**Constraint:** All model IDs are pinned. No floating aliases. No model is called unless its session feature is active.

---

## Guiding Principles

| Principle | Application |
|---|---|
| **Cheapest model that meets quality bar** | Use Haiku for classification and routing; reserve Opus for client-facing deliverables only |
| **Minimize vendor count** | Anthropic-first for all text tasks. OpenAI only for Whisper (no Anthropic STT). No redundant vendors. |
| **Fallback is always cheaper or same tier** | Degrading to fallback must not cost more than primary |
| **Batch what you can** | Chunking, embedding, localization are batched — never per-token streaming unless required |
| **Cache everything structural** | System prompts and state context are always in Anthropic prompt cache |

---

## Function → Model Map

### 1. Intent Classification

**What it does:** Classifies each BA turn into one of 8 intents so the pipeline can route correctly.

| | |
|---|---|
| **Primary** | `claude-haiku-4-5-20251001` |
| **Fallback** | `gemini-2.0-flash` |
| **Mode** | Single JSON object output, `<100 ms` target |
| **Why Haiku** | 8-way classification is a simple structured output task; Haiku's latency budget keeps the pipeline under 200 ms before the first token |
| **Cost estimate** | ~$0.001 per turn |

**Intent set:**
```
ProblemCapture | StakeholderProbe | RequirementCapture | ConstraintStatement
ArchitectureComment | ReviewFeedback | UploadRequest | Clarification
```

---

### 2. RAG-Based Search

**What it does:** Embeds the query, runs hybrid search (vector + BM25), and synthesises a ranked context block from retrieved chunks.

| | |
|---|---|
| **Embedding model** | `voyage-large-2` · 1536-dim |
| **Synthesis (post-retrieval)** | `claude-haiku-4-5-20251001` |
| **Fallback (synthesis)** | `gemini-2.0-flash` |
| **Mode** | Embedding is batched; synthesis is synchronous but short |
| **Why Voyage** | Already decided (Sprint 0). Best retrieval accuracy at this dimension for business documents |
| **Cost estimate** | ~$0.0001 per 1K tokens (Voyage) + ~$0.001 per synthesis call |

The search itself (pgvector + BM25) is pure database — no LLM needed. The LLM only synthesises the top-k chunks into a concise context block before the gap analyzer runs.

---

### 3. Visual Diagram Understanding

**What it does:** Interprets uploaded architecture diagrams, flowcharts, and wireframes to extract structured entities and relationships.

| | |
|---|---|
| **Primary** | `claude-sonnet-4-6` (multimodal) |
| **Fallback** | `gemini-2.0-flash` (multimodal) |
| **Mode** | Image + structured extraction prompt; response is JSON |
| **Why Sonnet not Opus** | Vision tasks do not require Opus-level reasoning; Sonnet's vision quality is equivalent for diagram interpretation at 40% lower cost |
| **Cost estimate** | ~$0.01–0.05 per diagram (image token cost dominates) |

Only fires when an image or diagram file is detected in the upload payload. Lazy-loaded — never initialised unless an image is present in the turn.

---

### 4. Document Exploration · Chunking · Embeddings

**What it does:** Ingests raw documents (PDF, DOCX, XLSX, images), splits them into semantically coherent chunks, scrubs PII, and embeds for retrieval.

| Sub-task | Model / Tool |
|---|---|
| Parsing (PDF/DOCX/XLSX) | `pypdf`, `python-docx`, `openpyxl` — rule-based, no LLM |
| Semantic chunk boundary detection | `claude-haiku-4-5-20251001` — only for boundary ambiguity; most splits are rule-based |
| PII scrubbing | `presidio-analyzer` — rule-based NER, no LLM |
| Embedding | `voyage-large-2` · batch mode (up to 128 chunks per API call) |
| Chunk metadata summarisation | `claude-haiku-4-5-20251001` |

**Fallback (embedding):** `text-embedding-3-small` (OpenAI, 1536-dim) — same dimension, compatible with existing pgvector columns.

**Mode:** Entire ingestion pipeline is async. Runs in the background after `IngestDocument` gRPC call returns `IngestAck`. No streaming.

**Cost estimate:** ~$0.0001 per chunk (Voyage embedding) + ~$0.002 per document (Haiku metadata). A 20-page PDF ≈ ~$0.01 total.

---

### 5. Output / BRD / SRS Creation

**What it does:** Generates the final client-facing Business Requirement Document or System Requirements Specification from the accumulated session state.

| | |
|---|---|
| **Primary** | `claude-opus-4-7` |
| **Fallback** | `claude-sonnet-4-6` |
| **Mode** | Long-form streaming; structured sections via tool_use |
| **Why Opus** | This is the only deliverable the client sees. Quality is the constraint. Opus is justified here and nowhere else. |
| **Cost estimate** | ~$0.50–$2.00 per BRD (20K–80K output tokens); amortised over the session lifetime |

Triggered only on transition to `ReviewAndSignOff` or explicit export. Never called during a regular turn. Budget check enforced before dispatch — if session is over budget, fall back to Sonnet automatically.

---

### 6. Data Transformations

**What it does:** Maps raw entity extractions to canonical schema fields, normalises duplicates, resolves naming conflicts between requirements, and produces structured JSON diffs.

| | |
|---|---|
| **Primary** | `claude-haiku-4-5-20251001` |
| **Fallback** | `gemini-2.0-flash` |
| **Mode** | `tool_use` / `response_format: json_object`; deterministic input → output |
| **Why Haiku** | Transformations are schema-mapping tasks. There is no creativity required — only precision and speed. |
| **Cost estimate** | ~$0.001–$0.003 per turn (batched with EntityExtractor call where possible) |

---

### 8. Requirement Refinement

**What it does:** Deduplicates, merges, and clarifies requirements accumulated across phases. Identifies contradictions and proposes resolution options for the BA to confirm.

| | |
|---|---|
| **Primary** | `claude-sonnet-4-6` |
| **Fallback** | `claude-haiku-4-5-20251001` |
| **Mode** | Structured streaming; produces a diff-like patch object |
| **Why Sonnet** | Refinement requires reading across many requirements simultaneously and reasoning about semantic overlap. Haiku makes errors on complex cross-requirement logic. |
| **Cost estimate** | ~$0.01–$0.05 per refinement pass (triggered at phase transition, not per turn) |

Runs at `ConstraintCapture → ArchitectureAlignment` transition and again before BRD generation to clean up the final requirements set.

---

### 9. Voice / Image to Text

**What it does:** Transcribes BA voice input to text and extracts structured text from scanned document images (non-diagram).

| Sub-task | Model | Vendor |
|---|---|---|
| Speech-to-text | `whisper-1` | OpenAI |
| Scanned doc / image OCR | `claude-sonnet-4-6` (multimodal) | Anthropic |
| **Fallback (STT)** | `gemini-2.0-flash` audio mode | Google |

**Why Whisper:** Best accuracy-to-cost ratio for STT at $0.006/min. No Anthropic equivalent exists. This is the only OpenAI API usage in the system.

**Why Sonnet for OCR:** Scanned documents are often partially degraded. Sonnet's multimodal understanding handles irregular layouts better than pure OCR tools.

**Cost estimate:** Whisper — $0.006 per minute of audio. OCR — ~$0.01–$0.03 per scanned page.

Lazy-loaded: voice client is only initialised when the turn payload includes an audio attachment; OCR client when a non-diagram image is present.

---

### 10. Localization

**What it does:** Translates the final BRD/SRS output to the client's target language after generation.

| | |
|---|---|
| **Primary** | `claude-haiku-4-5-20251001` |
| **Fallback** | `gemini-2.0-flash` |
| **Mode** | Batched; one section at a time to stay within context limits |
| **Why Haiku not DeepL** | Adding DeepL as a vendor adds ops overhead (another API key, another failure mode, another SDK). Haiku handles translation quality acceptably for business documents. Revisit for Phase 2 if quality benchmarks fail. |
| **Cost estimate** | ~$0.02–$0.10 per BRD translation (input + output tokens for a full document) |

Only fires when `session.target_locale != "en"`. Lazy-loaded. Runs after BRD is fully generated — never inline.

---

## Cost Budget Reference

| Tier | Model | Approx cost / 1M input tokens | Approx cost / 1M output tokens |
|---|---|---|---|
| Fast | `claude-haiku-4-5-20251001` | $0.80 | $4.00 |
| Standard | `claude-sonnet-4-6` | $3.00 | $15.00 |
| Premium | `claude-opus-4-7` | $15.00 | $75.00 |
| Fallback | `gemini-2.0-flash` | $0.075 | $0.30 |
| Embedding | `voyage-large-2` | $0.12 / 1M tokens | — |
| STT | `whisper-1` | $0.006 / min | — |

**Session budget guardrail:** $5.00 hard limit per session enforced in the `SessionLLMContext`. Calls requiring Opus are checked against remaining budget before dispatch. If budget is exhausted, Sonnet is substituted automatically, and the BA is notified in the UI.

---

## Function × Model Matrix (Summary)

| Function | Primary | Fallback | Tier |
|---|---|---|---|
| Intent classification | `claude-haiku-4-5-20251001` | `gemini-2.0-flash` | Fast |
| RAG synthesis | `claude-haiku-4-5-20251001` | `gemini-2.0-flash` | Fast |
| RAG embedding | `voyage-large-2` | `text-embedding-3-small` | Embedding |
| Visual diagram understanding | `claude-sonnet-4-6` | `gemini-2.0-flash` | Standard |
| Chunking boundary detection | `claude-haiku-4-5-20251001` | rule-based only | Fast |
| Chunk metadata | `claude-haiku-4-5-20251001` | skipped | Fast |
| Document embedding | `voyage-large-2` | `text-embedding-3-small` | Embedding |
| BRD / SRS output | `claude-opus-4-7` | `claude-sonnet-4-6` | Premium |
| Data transformations | `claude-haiku-4-5-20251001` | `gemini-2.0-flash` | Fast |
| Requirement refinement | `claude-sonnet-4-6` | `claude-haiku-4-5-20251001` | Standard |
| Speech to text | `whisper-1` | `gemini-2.0-flash` (audio) | Specialised |
| Image / scan OCR | `claude-sonnet-4-6` | `gemini-2.0-flash` | Standard |
| Localization | `claude-haiku-4-5-20251001` | `gemini-2.0-flash` | Fast |

---

> LLM Universe · Chitragupt · Sprint 1 · May 2026
