# Chitragupt — Project Readiness Report

**Generated:** 2026-05-23  
**Sprint:** Sprint 1 (in progress)  
**Probe:** `python scripts/test_connections.py`  
**Result: 8 / 11 checks PASS**

---

## Connection Probe — Current State

| # | Check | Status | Latency | Detail |
|---|---|---|---|---|
| 1 | OpenRouter · Fast (Haiku 4.5) | **PASS** | 5.3 s | `anthropic/claude-haiku-4.5` → PONG |
| 2 | OpenRouter · Standard (Sonnet 4.6) | **PASS** | 4.0 s | `anthropic/claude-sonnet-4.6` → PONG |
| 3 | OpenRouter · Premium (Opus 4.7) | **PASS** | 3.8 s | `anthropic/claude-opus-4.7` → PONG |
| 4 | OpenRouter · Fallback (Gemini 2.5 Flash) | **PASS** | 2.2 s | `google/gemini-2.5-flash` → PONG |
| 5 | OpenRouter · Primary Embedding | **PASS** | 1.5 s | `openai/text-embedding-3-small` dim=1536 |
| 6 | PostgreSQL · connection | **PASS** | 119 ms | PostgreSQL 18.2 on x86_64-windows |
| 7 | PostgreSQL · pgvector extension | **FAIL** | — | Extension not installed on PG18 |
| 8 | PostgreSQL · table `documents` | **PASS** | — | migration 0002 applied |
| 9 | PostgreSQL · table `document_chunks` | **FAIL** | — | Blocked by pgvector |
| 10 | PostgreSQL · table `cost_log` | **PASS** | — | migration 0004 applied |
| 11 | PostgreSQL · `hybrid_search()` function | **FAIL** | — | Blocked by pgvector |

---

## What Is Ready

### LLM Layer — 100% Operational

All five model tiers live and reachable through OpenRouter.

| Tier | Model | Role |
|---|---|---|
| Fast | `anthropic/claude-haiku-4.5` | Intent classification, chunking, localization |
| Standard | `anthropic/claude-sonnet-4.6` | Visual understanding, requirement refinement |
| Premium | `anthropic/claude-opus-4.7` | BRD generation (quality floor) |
| Fallback | `google/gemini-2.5-flash` | Cross-vendor circuit-breaker for all Anthropic tiers |
| Embedding | `openai/text-embedding-3-small` | Document + query embeddings (dim=1536) |

All calls route through `https://openrouter.ai/api/v1` using the OpenAI-compatible
`chat/completions` endpoint. Auth: `OPENROUTER_API_KEY` (set in `.env`).

### Database — Partially Ready

| Component | Status |
|---|---|
| PostgreSQL 18.2 (local) | Running, connection verified |
| `documents` table | Created — migration 0002 applied |
| `cost_log` table | Created — migration 0004 applied |
| Migration runner | `.\scripts\Apply-Migrations.ps1` — idempotent, tracks applied files |

### Code Structure

| Component | Status |
|---|---|
| 5 pipeline nodes (intent, entity, gap, guidance, revisit) | Written — need API format migration |
| `LLMFactory` | Updated — routes all calls through OpenRouter via OpenAI SDK |
| `OrchestrationConfig` | Reads from `config/orchestration.yaml` — all model IDs confirmed valid |
| Unit tests Domain 1 (Determinism) | 9 tests written |
| Unit tests Domain 2 (Edge Cases) | 20 tests written |
| PowerShell test harness | `scripts/Invoke-TestHarness.ps1` — domain-by-domain execution with findings report |
| CI (GitHub Actions) | Docker-first pipeline — passes cargo fmt + Rust unit tests |

---

## What Failed and Why

---

### FAIL-01 · pgvector not installed on PostgreSQL 18

**Affected checks:** #7, #9, #11  
**Root cause:** pgvector is a C extension that ships separately from PostgreSQL. The local
installation has PostgreSQL 18.2 but no `vector.dll` / `vector.control` files in the PG18
extension directories.

**Downstream impact:**
- `document_chunks` table cannot be created (uses `vector(1536)` column type)
- `hybrid_search()` SQL function cannot be created (uses `vector(1536)` in signature)
- The entire RAG retrieval path — embed → store → hybrid search → re-rank — is broken until this is resolved
- Integration tests that exercise the ingestion or retrieval pipeline will fail

**How to fix:**

```powershell
# Step 1 — Download pgvector binary for PG18 Windows
# Go to: https://github.com/pgvector/pgvector/releases
# Download: pgvector-vX.X.X-pg18-windows-x86_64.zip

# Step 2 — Copy files (adjust zip path)
$pgBase = "C:\Program Files\PostgreSQL\18"
Expand-Archive "pgvector-*.zip" -DestinationPath "$env:TEMP\pgvector"
Copy-Item "$env:TEMP\pgvector\vector.dll"       "$pgBase\lib\"
Copy-Item "$env:TEMP\pgvector\vector.control"   "$pgBase\share\extension\"
Copy-Item "$env:TEMP\pgvector\vector--*.sql"    "$pgBase\share\extension\"

# Step 3 — Apply remaining migrations
.\scripts\Apply-Migrations.ps1

# Step 4 — Verify
python scripts/test_connections.py
# Expected: 11/11 PASS
```

**Alternative (Docker):** When `docker compose up` is run, the `pgvector/pgvector:pg17`
image has pgvector pre-installed. The Docker path is the target for CI; local-without-Docker
is development convenience only.

---

### FAIL-02 · `intfloat/e5-large-v2` not available on OpenRouter

**Affected checks:** (would have been #5 if attempted)  
**Root cause:** OpenRouter's current catalog (358 models, queried live) contains no
dedicated embedding models. `intfloat/e5-large-v2` — a HuggingFace sentence-transformer
model — is not listed. OpenRouter does expose OpenAI's embedding endpoint, which is why
`openai/text-embedding-3-small` works.

**Resolution applied:** Primary embedding switched to `openai/text-embedding-3-small`
(dim=1536, confirmed live, latency 1.5 s). This maintains embedding dimension compatibility
with the vector store schema (which also expects 1536). Check #5 now passes.

**If `intfloat/e5-large-v2` is needed:** Run it locally via `sentence-transformers`:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("intfloat/e5-large-v2")
embeddings = model.encode(["query: probe"])  # dim=1024 — requires schema change
```
Note: e5-large-v2 outputs **1024-dim** vectors, not 1536. Using it would require altering
the `document_chunks.embedding` column type and rebuilding the HNSW index. Not recommended
while the vector namespace is unfixed.

---

### FAIL-03 · Agent code uses Anthropic SDK call format

**Affected checks:** (runtime, not probed)  
**Root cause:** The five pipeline node files call `client.messages.create(...)` (Anthropic
SDK style). `LLMFactory` now returns an `AsyncOpenAI` client (OpenAI SDK), which has
`client.chat.completions.create(...)` instead. A live pipeline run will raise
`AttributeError: 'AsyncOpenAI' object has no attribute 'messages'`.

**Status:** Deferred — unit tests use mocked clients so they are not affected.
Full migration is a Sprint 1 task before any live end-to-end pipeline run.

**Files to update:**
- `agents/intent_classifier.py`
- `agents/entity_extractor.py`
- `agents/gap_analyzer.py`
- `agents/guidance_generator.py` (streaming path also changes)
- `agents/revisit_handler.py`

---

## Remaining Blockers Before Sprint 1 Close

| Priority | Item | Est. Effort | Unblocks |
|---|---|---|---|
| P0 | Install pgvector for PG18, re-run migrations | 30 min | RAG pipeline, integration tests |
| P0 | Migrate 5 agent files to OpenAI SDK call format | 2–3 h | Live pipeline, end-to-end tests |
| P1 | Implement Domains 3–9 tests (TEST_PLAN.md) | 3 weeks | Sprint 1 exit criteria 6–9 |
| P2 | Upgrade `Voyage API key` (optional) | 15 min | Higher-quality embeddings |

---

## How to Re-Run the Probe

```powershell
python scripts/test_connections.py
```

Target state after pgvector install: **11 / 11 PASS**.

---

## Environment Summary

| Variable | Value (local dev) |
|---|---|
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `OPENROUTER_API_KEY` | Set ✓ |
| `MODEL_FAST` | `anthropic/claude-haiku-4.5` |
| `MODEL_STANDARD` | `anthropic/claude-sonnet-4.6` |
| `MODEL_PREMIUM` | `anthropic/claude-opus-4.7` |
| `MODEL_EMBEDDING` | `openai/text-embedding-3-small` |
| `MODEL_FALLBACK_ANTHROPIC` | `google/gemini-2.5-flash` |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:root@localhost:5432/chitragupt` |
| `POSTGRES_PASSWORD` | `root` (local only — Docker uses its own secret) |
| `VOYAGE_API_KEY` | Not set (embedding covered by OpenRouter) |

---

> Chitragupt · Sprint 1 Readiness · 2026-05-23 · Run `python scripts/test_connections.py` to refresh
