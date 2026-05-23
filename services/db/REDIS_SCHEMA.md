# Redis Key Schema — Chitragupt

**Version:** 1.0 — Sprint 1  
**Purpose:** Authoritative reference for all Redis key patterns, data types, TTL policies, and access owners.  
**Technology:** Redis 7 (single instance, MVP; Cluster upgrade is Sprint 3)

All keys are namespaced by `{workspace_id}` to maintain tenant isolation at the cache layer.
The pattern `{workspace_id}` is always the UUID of the workspace, not a human-readable slug.

---

## Key Catalogue

### 1. Budget Counters

These are the authoritative spend counters for each session. They are the source of truth for
`BudgetTracker.stage()` — not the in-process float. All increments use `INCRBYFLOAT` for atomicity.

| Key Pattern | Type | Owner | TTL |
|---|---|---|---|
| `budget:{workspace_id}:{session_id}:total_usd` | String (float) | Python ai-orchestration | 7 days after last write |
| `budget:{workspace_id}:{session_id}:{feature}:usd` | String (float) | Python ai-orchestration | 7 days after last write |
| `budget:{workspace_id}:{session_id}:stage` | String | Python ai-orchestration | 60 seconds (recomputed) |

**Notes:**
- `{feature}` matches the `LLMFeature` enum value (e.g., `INTENT_CLASSIFICATION`, `RAG_SYNTHESIS`).
- `stage` is a derived key set after every `record()` call: `NORMAL` | `CAUTION` | `CRITICAL` | `EXHAUSTED`.
- Budget stage TTL is intentionally short — it is recomputed from the total on cache miss.
- Total and per-feature keys use `EXPIRE` reset on every write, not a fixed expiry from creation.

**Operations used:**
```
INCRBYFLOAT budget:{wid}:{sid}:total_usd {delta}
EXPIRE      budget:{wid}:{sid}:total_usd 604800
GET         budget:{wid}:{sid}:total_usd
SET         budget:{wid}:{sid}:stage {stage} EX 60
```

---

### 2. Session State Cache

Hot cache for the Rust `SessionState` struct. Avoids a PostgreSQL round-trip on every pipeline turn.
Written by the Rust kernel after every successful state mutation. Read by Python before building pipeline input.

| Key Pattern | Type | Owner | TTL |
|---|---|---|---|
| `session:{workspace_id}:{session_id}:state` | String (JSON) | Rust state-machine | 30 minutes, sliding |

**Notes:**
- TTL is sliding: reset to 30 minutes on every read AND write (`GETEX` with `EX 1800`).
- On cache miss, the Rust kernel reads from PostgreSQL `sessions.state_blob` and repopulates.
- JSON format is the canonical `SessionState` struct serialised with `serde_json`.
- The cache must never be the only copy — PostgreSQL is the source of truth.

**Operations used:**
```
SET     session:{wid}:{sid}:state {json} EX 1800
GETEX   session:{wid}:{sid}:state EX 1800
DEL     session:{wid}:{sid}:state    -- on session termination
```

---

### 3. Document Ingestion Status

Tracks in-progress document ingestion jobs. Allows the upload endpoint to return immediately and
the BA to receive a notification when indexing completes.

| Key Pattern | Type | Owner | TTL |
|---|---|---|---|
| `doc:{workspace_id}:{document_id}:status` | String | Python ai-orchestration | 24 hours |
| `doc:{workspace_id}:{document_id}:progress` | String (int %) | Python ai-orchestration | 24 hours |
| `doc:{workspace_id}:{document_id}:error` | String | Python ai-orchestration | 24 hours |

**Status values:** `pending` → `ingesting` → `indexed` | `failed`

**Operations used:**
```
SET  doc:{wid}:{did}:status ingesting EX 86400
SET  doc:{wid}:{did}:progress 42 EX 86400
SET  doc:{wid}:{did}:status indexed EX 86400
SET  doc:{wid}:{did}:error  "chunk failed at page 7" EX 86400
```

---

### 4. Pipeline Turn Lock

Prevents concurrent pipeline runs for the same session (only one turn in flight at a time).
Acquired at the start of `PipelineExecutor.run()`, released when the turn completes.

| Key Pattern | Type | Owner | TTL |
|---|---|---|---|
| `lock:{workspace_id}:{session_id}:turn` | String | Python ai-orchestration | 30 seconds |

**Notes:**
- Set with `SET ... NX EX 30` (atomic acquire). If key exists, the new request is queued or rejected.
- 30-second TTL is a safety net against crash-without-release; the pipeline timeout budget is 26 seconds.
- Released with `DEL` on turn completion (success or abort).

**Operations used:**
```
SET  lock:{wid}:{sid}:turn 1 NX EX 30   -- returns OK on acquire, nil on contention
DEL  lock:{wid}:{sid}:turn
```

---

### 5. Pub/Sub Channels

Used for real-time notifications between services (document indexed, turn complete).
Subscribers are the gRPC servicer (for streaming) and the Rust kernel (for state updates).

| Channel Pattern | Publisher | Subscribers | Payload |
|---|---|---|---|
| `events:{workspace_id}:{session_id}:turn_complete` | Python ai-orchestration | Rust kernel | `{"turn_id": "...", "ac_updates": [...], "entities": [...]}` |
| `events:{workspace_id}:{document_id}:indexed` | Python ai-orchestration | gRPC servicer | `{"document_id": "...", "chunk_count": N, "status": "indexed"}` |

**Notes:**
- Pub/Sub is fire-and-forget. For guaranteed delivery, the canonical data is in PostgreSQL.
- Subscribers use `SUBSCRIBE` in a dedicated connection pool (not the same pool as commands).
- Payload is compact JSON; full entity data is fetched from PostgreSQL on receipt.

---

## TTL Summary

| Key Family | TTL | Refresh on Access |
|---|---|---|
| Budget counters (total, per-feature) | 7 days | Yes — reset on every write |
| Budget stage | 60 seconds | No — always recomputed |
| Session state cache | 30 minutes | Yes — sliding window |
| Document status | 24 hours | No |
| Turn lock | 30 seconds | No — intentional |
| Pub/Sub channels | No TTL | N/A |

---

## Key Naming Conventions

1. All separators are `:` (colon). No dots, no slashes.
2. UUIDs are lowercase, no braces: `a1b2c3d4-...`
3. Feature names in budget keys match the Python `LLMFeature` enum exactly (uppercase snake_case).
4. Never use human-readable slugs or usernames as key components — always UUIDs.
5. The `{workspace_id}` prefix must appear in every key. There are no global (cross-tenant) keys.

---

## What Is NOT in Redis

| Data | Why Not Redis | Where It Lives |
|---|---|---|
| Session entity lists (actors, requirements) | Durability required | PostgreSQL `actors`, `requirements` |
| AC status | Rust kernel owns writes; must survive restart | PostgreSQL `ac_status` |
| Document chunks and embeddings | Size and index complexity | PostgreSQL `document_chunks` + pgvector |
| Raw uploaded files | Size; CDN delivery | Cloudflare R2 |
| Audit trail | Immutable append-only | PostgreSQL `cost_log`, `phase_history` |

---

> Chitragupt · Redis Key Schema · Sprint 1 · May 2026
