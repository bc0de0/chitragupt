# Sprint 1 — Connectivity & Integration Report

**Date:** 2026-05-23  
**Scope:** OpenRouter LLM API, PostgreSQL 18, pgvector, RAG pipeline readiness  
**Probe script:** `scripts/test_connections.py`  
**Migrations:** `services/ai-orchestration/migrations/`

---

## Executive Summary

**6 of 12 checks passed.** The database and two LLM tiers (Sonnet, Opus) are reachable.
Three categories of blockers remain before the full pipeline can run end-to-end:

| Category | Status | Blocker |
|---|---|---|
| OpenRouter — Sonnet / Opus | **PASS** | — |
| OpenRouter — Haiku (fast tier) | **FAIL** | Wrong model ID in config |
| OpenRouter — Gemini fallback | **FAIL** | Wrong model ID in config |
| OpenRouter — text-embedding-3-small | **PASS** | — |
| Voyage embeddings | **FAIL** | VOYAGE_API_KEY not set |
| PostgreSQL connection | **PASS** | — |
| pgvector extension | **FAIL** | Extension not installed on PG18 |
| Table: documents | **PASS** | migration 0002 applied |
| Table: document_chunks | **FAIL** | Blocked by pgvector |
| Table: cost_log | **PASS** | migration 0004 applied |
| hybrid_search() function | **FAIL** | Blocked by pgvector |
| Full RAG pipeline | **BLOCKED** | Needs pgvector + correct model IDs |

---

## Detailed Findings

---

### FINDING-01 — Haiku model ID is invalid on OpenRouter

**Status:** FAIL  
**Probe:** `OpenRouter/Fast (Haiku)`  
**Error:** `anthropic/claude-haiku-4-5-20251001 is not a valid model ID`

**Root cause:** OpenRouter's model catalog uses shortened slugs without the date suffix
for some Anthropic models. `claude-sonnet-4-6` and `claude-opus-4-7` are accepted but
`claude-haiku-4-5-20251001` is not registered under that exact slug.

**Fix required:**

1. Check OpenRouter's current model list for the correct Haiku slug:
   ```
   curl -s https://openrouter.ai/api/v1/models \
     -H "Authorization: Bearer $OPENROUTER_API_KEY" | python -m json.tool | grep haiku
   ```
2. Update `.env`:
   ```
   MODEL_FAST=anthropic/claude-haiku-3-5           # likely correct slug
   ```
3. Update `services/ai-orchestration/config/orchestration.yaml`:
   ```yaml
   fast: "anthropic/claude-haiku-3-5"
   ```

**Likely correct slugs to try (in order):**
- `anthropic/claude-haiku-3-5`
- `anthropic/claude-3-5-haiku`
- `anthropic/claude-haiku-4-5`

---

### FINDING-02 — Gemini fallback model ID is invalid on OpenRouter

**Status:** FAIL  
**Probe:** `OpenRouter/Fallback (Gemini)`  
**Error:** `google/gemini-2.0-flash is not a valid model ID`

**Root cause:** Same as FINDING-01 — the Gemini model slug on OpenRouter may differ from
the Google-internal model name.

**Fix required:**

1. Query OpenRouter for Google model slugs:
   ```
   curl -s https://openrouter.ai/api/v1/models | python -m json.tool | grep google
   ```
2. Update `.env`:
   ```
   MODEL_FALLBACK_ANTHROPIC=google/gemini-2.0-flash-exp    # common slug
   MODEL_FALLBACK_STT=google/gemini-2.0-flash-exp
   ```

**Likely correct slugs:**
- `google/gemini-2.0-flash-exp`
- `google/gemini-flash-2.0`
- `google/gemini-2.0-flash-001`

---

### FINDING-03 — VOYAGE_API_KEY not set

**Status:** FAIL  
**Probe:** `Voyage/embed`  
**Error:** `VOYAGE_API_KEY not set in .env`

**Root cause:** The `.env` file has `VOYAGE_API_KEY=` (empty). Voyage AI is the primary
embedding provider (`voyage-large-2`) and is NOT available through OpenRouter — it requires
a separate API key from dash.voyageai.com.

**Impact:**
- Voyage embeddings unavailable → document ingestion pipeline is broken
- `embedding` tier in `OrchestrationConfig` has no functional client
- All tests requiring embeddings will fail

**Fix required:**
1. Get a Voyage API key from `https://dash.voyageai.com`
2. Set in `.env`:
   ```
   VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

**Fallback path while awaiting Voyage key:**
Change `MODEL_EMBEDDING` to `openai/text-embedding-3-small` temporarily. This uses
OpenRouter (which works, dim=1536 confirmed) but loses the Voyage-quality embeddings
that the system was designed for. Mixed-model embeddings break similarity search —
do not index any real documents under the fallback until you switch back to Voyage.

---

### FINDING-04 — pgvector extension not installed on PostgreSQL 18

**Status:** FAIL  
**Probe:** `PostgreSQL/pgvector`  
**Error:** `pgvector extension NOT installed`

**Root cause:** pgvector is a C extension that must be compiled against the specific
PostgreSQL major version. The local installation has PostgreSQL 18.2 but no pgvector
binary for PG18.

**Downstream impact:**
- Migration `0003_create_document_chunks.sql` cannot run (`vector(1536)` type unknown)
- Migration `0005_create_hybrid_search_fn.sql` cannot run
- RAG pipeline has no vector store — document ingestion fails at the embed+insert step
- `hybrid_search()` function unavailable — `RAGRetrievalNode` cannot execute

**Fix options (in recommended order):**

**Option A — Install pgvector binary for PG18 (recommended)**
```powershell
# Download pgvector for PG18 Windows from: https://github.com/pgvector/pgvector/releases
# Look for: pgvector-v0.x.x-pg18-windows-x86_64.zip
# Then extract and copy:
#   vector.dll        → C:\Program Files\PostgreSQL\18\lib\
#   vector.control    → C:\Program Files\PostgreSQL\18\share\extension\
#   vector--*.sql     → C:\Program Files\PostgreSQL\18\share\extension\

# After copying files, enable the extension:
psql -U postgres -d chitragupt -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Then re-run migrations:
.\scripts\Apply-Migrations.ps1
```

**Option B — Use Docker (deferred to Sprint 2 integration phase)**
When running `docker compose up`, the `pgvector/pgvector:pg17` image has pgvector
pre-installed. For local development without Docker, Option A is required.

**Option C — Downgrade to PG17 locally**
pgvector has confirmed PG17 Windows binaries. If upgrading pgvector is blocked,
install PostgreSQL 17 locally and point `DATABASE_URL` at the PG17 instance.

---

### FINDING-05 — Table `document_chunks` missing (blocked by pgvector)

**Status:** FAIL  
**Probe:** `PostgreSQL/table:document_chunks`

**Root cause:** Migration `0003_create_document_chunks.sql` requires the `vector(1536)`
type from pgvector. Since pgvector is not installed, this migration was skipped with an
error during `Apply-Migrations.ps1`.

**Fix:** Install pgvector (FINDING-04) then re-run `.\scripts\Apply-Migrations.ps1`.

---

### FINDING-06 — `hybrid_search()` function missing (blocked by pgvector)

**Status:** FAIL  
**Probe:** `PostgreSQL/hybrid_search()`

**Root cause:** Migration `0005_create_hybrid_search_fn.sql` requires `vector(1536)` in its
function signature. Same blocker as FINDING-05.

---

### FINDING-07 — Agent code uses Anthropic SDK format, factory now returns OpenAI client

**Status:** CODE DEBT — not blocking probes, will block runtime  
**Affected files:** All 5 agent files in `src/ai_orchestration/agents/`

**Root cause:** OpenRouter is OpenAI-compatible only (exposes `/chat/completions`, not
Anthropic's `/messages`). The factory now correctly returns an `AsyncOpenAI` client for
all text-generation calls. However, the existing agent code calls:
```python
resp = await client.messages.create(model=..., messages=[...])
```
This is the Anthropic SDK API — it does not exist on the OpenAI client.

**Impact:** Every agent call will raise `AttributeError: 'AsyncOpenAI' has no attribute 'messages'`
when running against the real factory in a live environment. (Unit tests are not affected
because they mock the client entirely.)

**Fix required (Sprint 1 agent migration task):**

Replace all `client.messages.create(...)` calls with `client.chat.completions.create(...)`:

```python
# OLD (Anthropic SDK format)
resp = await client.messages.create(
    model=model_id,
    max_tokens=512,
    temperature=0,
    system="...",
    messages=[{"role": "user", "content": user_msg}],
)
text = resp.content[0].text

# NEW (OpenAI SDK format — OpenRouter compatible)
resp = await client.chat.completions.create(
    model=model_id,
    max_tokens=512,
    temperature=0,
    messages=[
        {"role": "system", "content": "..."},
        {"role": "user", "content": user_msg},
    ],
)
text = resp.choices[0].message.content
```

Streaming is also different:
```python
# OLD (Anthropic streaming)
async with client.messages.stream(...) as stream:
    async for text in stream.text_stream: yield text

# NEW (OpenAI streaming)
async with await client.chat.completions.create(..., stream=True) as stream:
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

**Files to update:**
- `agents/intent_classifier.py` — `_classify()` method
- `agents/entity_extractor.py` — `_extract()` method
- `agents/gap_analyzer.py` — `_analyze()` method
- `agents/guidance_generator.py` — `_generate()` method (streaming)
- `agents/revisit_handler.py` — `_handle()` method

---

## What is Working

| Component | Status | Detail |
|---|---|---|
| OpenRouter — Standard (Sonnet) | **LIVE** | `reply='PONG'` at 5.2s |
| OpenRouter — Premium (Opus) | **LIVE** | `reply='PONG'` at 4.4s |
| OpenRouter — Embedding fallback | **LIVE** | dim=1536, 3.2s |
| PostgreSQL 18 connection | **LIVE** | asyncpg at 134ms |
| Table: `documents` | **READY** | migration 0002 applied |
| Table: `cost_log` | **READY** | migration 0004 applied |
| Migration runner | **READY** | `.\scripts\Apply-Migrations.ps1` |

---

## Action Plan to Reach Full Pipeline

| Priority | Action | Owner | Blocker |
|---|---|---|---|
| P0 | Install pgvector for PG18 (FINDING-04) | Dev | None |
| P0 | Re-run migrations after pgvector install | Dev | pgvector install |
| P0 | Fix Haiku model ID in `.env` and `orchestration.yaml` (FINDING-01) | Dev | None |
| P0 | Fix Gemini model ID in `.env` (FINDING-02) | Dev | None |
| P1 | Add VOYAGE_API_KEY to `.env` (FINDING-03) | BA/Dev | API key procurement |
| P1 | Migrate 5 agent files from Anthropic SDK to OpenAI SDK format (FINDING-07) | Dev | None |
| P2 | Re-run `test_connections.py` to verify all 12 checks pass | Dev | P0 + P1 items |
| P2 | Run Domain 1 + 2 unit tests via `Invoke-TestHarness.ps1` | Dev | None (mocked) |

---

## How to Re-Run the Probe

```powershell
# After addressing the blockers above:
python scripts/test_connections.py

# Expected outcome: 12/12 checks passing
```

---

> Generated: 2026-05-23 · Chitragupt Sprint 1 · Connection Probe v1
