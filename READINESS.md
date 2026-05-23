# Chitragupt — Project Readiness Report

**Generated:** 2026-05-23  
**Sprint:** Sprint 1 (in progress)  
**Probe:** `python scripts/test_connections.py`  
**Result: 8 / 11 checks PASS** · Remaining 3 are pgvector (Docker-first, deferred)

---

## Connection Probe — Current State

| # | Check | Status | Latency | Detail |
|---|---|---|---|---|
| 1 | OpenRouter · Fast (Haiku 4.5) | **PASS** | 4.5 s | `anthropic/claude-haiku-4.5` → PONG |
| 2 | OpenRouter · Standard (Sonnet 4.6) | **PASS** | 4.8 s | `anthropic/claude-sonnet-4.6` → PONG |
| 3 | OpenRouter · Premium (Opus 4.7) | **PASS** | 3.2 s | `anthropic/claude-opus-4.7` → PONG |
| 4 | OpenRouter · Fallback (Gemini 2.5 Flash) | **PASS** | 1.7 s | `google/gemini-2.5-flash` → PONG |
| 5 | OpenRouter · Primary Embedding | **PASS** | 1.5 s | `google/gemini-embedding-001` dim=3072 ✓ |
| 6 | PostgreSQL · connection | **PASS** | 180 ms | PostgreSQL 18.2 on x86_64-windows |
| 7 | PostgreSQL · pgvector extension | **DEFERRED** | — | Docker image has it pre-installed |
| 8 | PostgreSQL · table `documents` | **PASS** | — | migration 0002 applied |
| 9 | PostgreSQL · table `document_chunks` | **DEFERRED** | — | Needs pgvector (Docker) |
| 10 | PostgreSQL · table `cost_log` | **PASS** | — | migration 0004 applied |
| 11 | PostgreSQL · `hybrid_search()` function | **DEFERRED** | — | Needs pgvector (Docker) |

---

## What Is Ready

### LLM Layer — 100% Operational

All five model tiers live and reachable through OpenRouter (25 embedding models catalogued,
live-probed to select the best).

| Tier | Model | Dim | Ctx | Role |
|---|---|---|---|---|
| Fast | `anthropic/claude-haiku-4.5` | — | — | Intent classification, chunking, localization |
| Standard | `anthropic/claude-sonnet-4.6` | — | — | Visual understanding, requirement refinement |
| Premium | `anthropic/claude-opus-4.7` | — | — | BRD generation (quality floor) |
| Fallback text | `google/gemini-2.5-flash` | — | — | Cross-vendor circuit-breaker |
| **Embedding** | **`google/gemini-embedding-001`** | **3072** | **20 000** | Document + query embeddings |
| Embed fallback | `openai/text-embedding-3-large` | 3072 | 8 192 | Same dimension — safe swap |

**Why `google/gemini-embedding-001`:** Largest context window (20 000 tokens) of any model
on OpenRouter's embedding catalog — crucial for long BA documents. Same 3072-dim output as
`text-embedding-3-large` so the fallback is a true zero-schema-change swap. $0.15/1M tokens.

All calls route through `https://openrouter.ai/api/v1`. Embedding calls use the
`/embeddings` endpoint; generation calls use `/chat/completions` (OpenAI-compatible).
Auth: `OPENROUTER_API_KEY` (set in `.env`).

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

### NOTE · Embedding model selection — full OpenRouter catalog surveyed

`intfloat/e5-large-v2` **IS** available on OpenRouter (queried via `?output_modalities=embeddings`
— 25 models returned). Earlier probe used the wrong filter and returned zero results.

Live dimension probe across top candidates:

| Model | Dim | Latency | Price/1M | Notes |
|---|---|---|---|---|
| `google/gemini-embedding-001` | 3072 | 1.4 s | $0.15 | **Selected** — largest ctx (20k) |
| `openai/text-embedding-3-large` | 3072 | 1.2 s | $0.13 | Fallback — same dim |
| `intfloat/e5-large-v2` | 1024 | 2.0 s | $0.01 | Available but 1024-dim (schema mismatch) |
| `qwen/qwen3-embedding-8b` | 4096 | 1.2 s | $0.01 | 4096-dim (schema mismatch) |

Vector schema updated to `vector(3072)` in migrations 0003 and 0005.
No documents indexed yet so the dimension change is safe.

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
| `MODEL_EMBEDDING` | `google/gemini-embedding-001` (dim=3072) |
| `MODEL_FALLBACK_ANTHROPIC` | `google/gemini-2.5-flash` |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:root@localhost:5432/chitragupt` |
| `POSTGRES_PASSWORD` | `root` (local only — Docker uses its own secret) |
| `PGVECTOR_DIMENSION` | `3072` (matches `google/gemini-embedding-001`) |
| `VOYAGE_API_KEY` | Not set (covered by `google/gemini-embedding-001` via OpenRouter) |

---

> Chitragupt · Sprint 1 Readiness · 2026-05-23 · Run `python scripts/test_connections.py` to refresh
