# Database Strategy — Chitragupt

**Status:** Authoritative for Sprint 1 implementation
**Scope:** All three storage layers — structured (PostgreSQL), cached (Redis), object (S3)
**Companion documents:**
- `LLM_UNIVERSE.md` — model assignments and cost tracking
- `LLM_DESIGN_PATTERNS.md` — session-scoped LLM factory and Redis budget tracking
- `docs/architecture/ontology.md` — canonical entity schemas
- `docs/architecture/TECH_STACK.md` — service ownership model

---

## Overview

Chitragupt uses three purpose-built storage layers. Each layer handles a distinct class of data; no layer is a substitute for another.

| Layer | Technology | Purpose |
|---|---|---|
| **Structured + Vector** | PostgreSQL 16 + pgvector | All relational entities, vector embeddings, audit trail, cost logs |
| **Cache + Events** | Redis 7 | Session state hot cache, budget counters, pub/sub event bus |
| **Object Storage** | S3 (or R2-compatible) | Raw uploaded documents, generated export artifacts |

All three services (Rust, Python, Go) connect to the same PostgreSQL and Redis instances. Each service uses its own connection pool and writes only to the tables it owns. No service reads from another service's tables directly — cross-service data access goes through gRPC.

---

## 1. Structured Storage — PostgreSQL 16 + pgvector

### 1.1 Why a Single PostgreSQL Instance

Rather than splitting relational and vector storage into separate systems, all data lives in one PostgreSQL instance extended with `pgvector`. This means:

- **Unified RLS**: Row-level security policies enforcing `tenant_id` isolation are written once, in one place, and apply consistently to every query — including vector similarity searches.
- **Transactional consistency**: When a document is ingested and its chunks are indexed, the document status update and the chunk inserts happen in the same transaction. There is no window where a document is marked `indexed` but its chunks are not yet visible.
- **Reduced operational surface**: One database to back up, replicate, and monitor rather than two.
- **Join capability**: Requirements can be retrieved together with their supporting chunk content in a single query, without cross-service round trips.

The tradeoff is that pgvector's ANN index performance does not yet match purpose-built vector databases at very high vector counts. The mitigation is HNSW indexing with carefully tuned parameters — this is sufficient for the MVP scale (estimated < 10M chunks per deployment). Re-evaluation against dedicated vector infrastructure is a Sprint 3 concern.

---

### 1.2 Service Ownership — Which Service Owns Which Tables

Each table is owned by exactly one service. Only the owning service issues `INSERT`, `UPDATE`, and `DELETE` on that table. Other services may read with `SELECT` where necessary, but never mutate.

| Table | Owning Service | Read By |
|---|---|---|
| `session` | **Rust** | Rust, Go (auth only — session existence check) |
| `workspace` | **Go** | All services (tenant_id resolution) |
| `user` | **Go** | Go, Rust (permission check) |
| `project` | **Go** | All services |
| `document` | **Python** | Python, Rust (document_id → gate resolution) |
| `chunk` | **Python** | Python only |
| `requirement` | **Python** | Python, Rust (via entity updates in SessionState) |
| `constraint` | **Python** | Python, Rust |
| `assumption` | **Python** | Python |
| `actor` | **Python** | Python, Rust |
| `conflict` | **Python** | Python |
| `gap` | **Python** | Python |
| `specification` | **Python** | Python, Go (export trigger) |
| `export_artifact` | **Python** | Go (presigned URL generation) |
| `client_sign_off` | **Go** | Go, Rust (sign-off gate resolution) |
| `llm_call_log` | **Python** | Rust (cost attribution rollup) |
| `audit_log` | **All** (append-only) | — |
| `domain_template` | **Go** (seeded) | All services |
| `brd_template` | **Go** (seeded) | Python (BRD generation) |

---

### 1.3 Row-Level Security (RLS)

RLS is enforced on every table that carries tenant-specific data. The pattern is identical across all tables:

```sql
-- Applied to every tenant-scoped table
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON <table_name>
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

The application layer sets `app.current_tenant_id` at connection time using the validated JWT claim. Every query then automatically scopes to the caller's tenant without any application-level WHERE clause required.

**Critical invariant:** No query against a tenant-scoped table is permitted without `app.current_tenant_id` set. A missing setting raises an error rather than returning rows from all tenants.

The `audit_log` and `llm_call_log` tables carry `tenant_id` columns but are append-only — `UPDATE` and `DELETE` are revoked from all application roles on these tables.

---

### 1.4 Core Table Schemas

The following schemas are derived directly from the ontology. Only Sprint 1 tables are specified here; tables required for Sprint 2 outputs (Specification, ExportArtifact, ClientSignOff) are stubbed as empty tables to allow FK references.

#### `session`

Owned by the Rust state machine. `state` is a JSONB blob serialized from `SessionState`. Updated atomically on every successful turn.

```sql
CREATE TABLE session (
  session_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id      UUID        NOT NULL REFERENCES workspace(workspace_id),
  project_id        UUID        NOT NULL REFERENCES project(project_id),
  user_id           UUID        NOT NULL REFERENCES "user"(user_id),
  tenant_id         UUID        NOT NULL,
  session_type      TEXT        NOT NULL CHECK (session_type IN ('elicitation','review','export','re_generation')),
  current_phase     TEXT        NOT NULL,
  state             JSONB       NOT NULL,         -- full SessionState blob
  started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at          TIMESTAMPTZ,
  pii_scrubbed      BOOLEAN     NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_session_project   ON session(project_id);
CREATE INDEX idx_session_tenant    ON session(tenant_id);
CREATE INDEX idx_session_state_gin ON session USING gin(state);
```

The GIN index on `state` enables queries like "find all sessions where a specific document_id is in `documents_indexed`" — needed by the gate resolution query when an upload completes.

#### `document`

```sql
CREATE TABLE document (
  document_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        UUID        NOT NULL REFERENCES project(project_id),
  tenant_id         UUID        NOT NULL,
  name              TEXT        NOT NULL,
  source_type       TEXT        NOT NULL,
  source_uri        TEXT,
  author            TEXT,
  version_label     TEXT,
  file_hash         TEXT,
  status            TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','indexed','failed','tombstoned')),
  trust_tier        INTEGER     NOT NULL CHECK (trust_tier BETWEEN 1 AND 5),
  is_superseded     BOOLEAN     NOT NULL DEFAULT FALSE,
  superseded_by     UUID        REFERENCES document(document_id),
  ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_modified_at  TIMESTAMPTZ,
  metadata          JSONB
);

CREATE INDEX idx_document_project ON document(project_id);
CREATE INDEX idx_document_status  ON document(status);
```

#### `chunk` — the vector table

The central table for RAG retrieval. The `embedding` column uses pgvector's `vector(1536)` type — matching `voyage-large-2` output dimension, which is fixed. The `sparse_vector` column stores BM25 weights as a JSON object `{term: weight}` for hybrid search.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunk (
  chunk_id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id         UUID          NOT NULL REFERENCES document(document_id),
  tenant_id           UUID          NOT NULL,
  project_id          UUID          NOT NULL,
  content             TEXT          NOT NULL,
  embedding           vector(1536)  NOT NULL,
  sparse_vector       JSONB,                      -- BM25 term weights
  chunk_index         INTEGER       NOT NULL,
  token_count         INTEGER       NOT NULL,
  start_char          INTEGER,
  end_char            INTEGER,
  page_number         INTEGER,
  section_title       TEXT,
  source_type         TEXT          NOT NULL,
  trust_tier          INTEGER       NOT NULL,
  confidence_modifier FLOAT         DEFAULT 0.0,
  valid_from          TIMESTAMPTZ   NOT NULL DEFAULT now(),
  valid_until         TIMESTAMPTZ,
  is_active           BOOLEAN       NOT NULL DEFAULT TRUE,
  language            TEXT          NOT NULL DEFAULT 'en'
);

-- HNSW index for approximate nearest-neighbour search (cosine distance)
-- m=16, ef_construction=64 — good balance of build time vs. query accuracy for this scale
CREATE INDEX idx_chunk_embedding_hnsw
  ON chunk USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Covering index for mandatory retrieval filters — scans this before touching the HNSW index
CREATE INDEX idx_chunk_tenant_project_active
  ON chunk(tenant_id, project_id, is_active)
  WHERE is_active = TRUE;

CREATE INDEX idx_chunk_document ON chunk(document_id);
```

**Why HNSW over IVFFlat:** HNSW does not require a training phase (`VACUUM` + `ANALYZE` cycle) and performs well on fresh inserts — important because chunks are inserted continuously as documents are ingested. IVFFlat requires a full table scan to build cluster centroids, making it unsuitable for tables that grow incrementally.

#### `requirement`

```sql
CREATE TABLE requirement (
  requirement_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id          UUID          NOT NULL REFERENCES project(project_id),
  tenant_id           UUID          NOT NULL,
  req_code            TEXT          NOT NULL,
  type                TEXT          NOT NULL,
  category            TEXT,
  description         TEXT          NOT NULL,
  priority            TEXT          NOT NULL DEFAULT 'should_have',
  source_chunks       UUID[]        NOT NULL DEFAULT '{}',
  confidence_score    FLOAT         NOT NULL,
  confidence_tier     TEXT          NOT NULL,
  status              TEXT          NOT NULL DEFAULT 'draft',
  acceptance_criteria JSONB,
  affected_actors     UUID[]        DEFAULT '{}',
  conflicts_with      UUID[]        DEFAULT '{}',
  depends_on          UUID[]        DEFAULT '{}',
  version             INTEGER       NOT NULL DEFAULT 1,
  created_by_agent    TEXT          NOT NULL,
  last_modified_by    TEXT          NOT NULL,
  created_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),
  approved_at         TIMESTAMPTZ,
  approved_by         UUID,
  human_override_text TEXT,
  UNIQUE(project_id, req_code)
);

CREATE INDEX idx_requirement_project ON requirement(project_id);
CREATE INDEX idx_requirement_status  ON requirement(status);
```

#### `requirement_version` — immutable audit trail

```sql
CREATE TABLE requirement_version (
  version_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  requirement_id      UUID        NOT NULL REFERENCES requirement(requirement_id),
  version             INTEGER     NOT NULL,
  description         TEXT        NOT NULL,
  status              TEXT        NOT NULL,
  confidence_score    FLOAT       NOT NULL,
  modified_by         TEXT        NOT NULL,
  modification_reason TEXT,
  diff_from_previous  TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(requirement_id, version)
);
```

A trigger on `requirement` inserts a `requirement_version` row on every UPDATE. This table is append-only — no application role has UPDATE or DELETE on it.

#### `llm_call_log`

Every LLM API call is written here by the Python service after the call completes. This is the authoritative cost record.

```sql
CREATE TABLE llm_call_log (
  call_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        UUID        NOT NULL REFERENCES project(project_id),
  tenant_id         UUID        NOT NULL,
  session_id        UUID        REFERENCES session(session_id),
  agent_name        TEXT        NOT NULL,
  model_id          TEXT        NOT NULL,
  model_tier        TEXT        NOT NULL,
  prompt_tokens     INTEGER     NOT NULL,
  completion_tokens INTEGER     NOT NULL,
  cached_tokens     INTEGER     NOT NULL DEFAULT 0,
  cost_usd          NUMERIC(10,6) NOT NULL,
  latency_ms        INTEGER     NOT NULL,
  success           BOOLEAN     NOT NULL,
  error_code        TEXT,
  fallback_used     BOOLEAN     NOT NULL DEFAULT FALSE,
  timestamp         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_llm_call_project   ON llm_call_log(project_id, timestamp DESC);
CREATE INDEX idx_llm_call_session   ON llm_call_log(session_id);
CREATE INDEX idx_llm_call_model     ON llm_call_log(model_id);
```

The Python service's `BudgetTracker` writes to Redis for fast per-turn budget checks (see Section 2.2) but writes the authoritative record here after each call. Rust reads aggregated cost via a `ProjectCostSummary` materialized view.

#### `audit_log`

All services write here. No service reads it at runtime — it is for compliance and operational post-mortems only.

```sql
CREATE TABLE audit_log (
  log_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID        NOT NULL,
  project_id    UUID,
  actor_type    TEXT        NOT NULL CHECK (actor_type IN ('human','agent','system')),
  actor_id      TEXT        NOT NULL,
  action        TEXT        NOT NULL,
  entity_type   TEXT        NOT NULL,
  entity_id     UUID        NOT NULL,
  before_state  JSONB,
  after_state   JSONB,
  metadata      JSONB,
  timestamp     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_tenant_ts  ON audit_log(tenant_id, timestamp DESC);
CREATE INDEX idx_audit_entity     ON audit_log(entity_type, entity_id);
```

---

### 1.5 Hybrid Search Query Pattern

Every RAG retrieval uses a hybrid query: dense vector similarity (pgvector cosine) combined with BM25 sparse score, then re-ranked. This is the canonical retrieval query executed by the Python `RAGRetrievalNode`.

```sql
-- Hybrid retrieval: dense + sparse, filtered by mandatory tenant/project/active gates
WITH dense AS (
  SELECT
    chunk_id,
    1 - (embedding <=> $query_embedding) AS dense_score
  FROM chunk
  WHERE
    tenant_id  = $tenant_id        -- mandatory: never relaxed
    AND project_id = $project_id   -- mandatory: session scope
    AND is_active  = TRUE           -- mandatory: exclude tombstoned
    AND (valid_until IS NULL OR valid_until > now())
  ORDER BY embedding <=> $query_embedding
  LIMIT 50
),
bm25_candidates AS (
  -- Sparse BM25 score computed application-side; this join pulls content for scoring
  SELECT chunk_id, content, sparse_vector
  FROM chunk
  WHERE
    tenant_id  = $tenant_id
    AND project_id = $project_id
    AND is_active  = TRUE
    AND chunk_id   = ANY($candidate_ids)  -- candidates pre-filtered in Python via BM25
)
SELECT
  d.chunk_id,
  c.content,
  c.section_title,
  c.page_number,
  c.trust_tier,
  c.confidence_modifier,
  d.dense_score,
  ($bm25_weight * b.bm25_score + (1 - $bm25_weight) * d.dense_score) AS hybrid_score
FROM dense d
JOIN chunk c USING (chunk_id)
LEFT JOIN bm25_candidates b USING (chunk_id)
ORDER BY hybrid_score DESC
LIMIT $top_k;
```

BM25 scoring is computed in Python using `rank-bm25` before this query runs. The application passes `$candidate_ids` (top-100 BM25 matches) and `$bm25_weight` (default: 0.3). The database handles the dense vector side; Python merges the scores.

The mandatory filters `(tenant_id, project_id, is_active)` are always applied before the ANN index is invoked — the covering index `idx_chunk_tenant_project_active` ensures this pre-filter is cheap.

---

### 1.6 Materialized Views

Two materialized views are refreshed on a schedule (every 15 minutes) and on-demand after BRD generation:

```sql
-- Per-project cost summary — read by Rust for budget attribution display
CREATE MATERIALIZED VIEW project_cost_summary AS
SELECT
  project_id,
  tenant_id,
  SUM(cost_usd)                                   AS total_cost_usd,
  jsonb_object_agg(agent_name, agent_cost)        AS cost_by_agent,
  jsonb_object_agg(model_id,   model_cost)        AS cost_by_model,
  SUM(cached_tokens * 0.0000008)                  AS prompt_cache_savings_usd,
  COUNT(*)                                        AS total_calls,
  SUM(prompt_tokens + completion_tokens)          AS total_tokens,
  now()                                           AS last_calculated_at
FROM (
  SELECT
    project_id, tenant_id, agent_name, model_id,
    cost_usd,
    cached_tokens,
    prompt_tokens,
    completion_tokens,
    SUM(cost_usd) OVER (PARTITION BY project_id, agent_name) AS agent_cost,
    SUM(cost_usd) OVER (PARTITION BY project_id, model_id)  AS model_cost
  FROM llm_call_log
) t
GROUP BY project_id, tenant_id;

CREATE UNIQUE INDEX ON project_cost_summary(project_id);
```

---

## 2. Cache Layer — Redis 7

### 2.1 Why Redis

Redis handles three distinct concerns — none of which belong in PostgreSQL:

1. **Session state hot cache**: loading `SessionState` from PostgreSQL on every turn would add 5–20ms per request. Redis keeps the current state in memory for active sessions.
2. **Budget counters**: per-session and per-project spend accumulators that update on every LLM call. These require atomic increment semantics (`INCRBYFLOAT`), not row locks.
3. **Event bus**: asynchronous notifications between services (upload complete, sign-off received, budget threshold). These do not require durable storage — a service restart drops unconsumed messages, which is acceptable for these event types.

### 2.2 Key Namespaces and Data Structures

All keys are namespaced to prevent collisions across concerns:

| Namespace | Structure | TTL | Owner | Purpose |
|---|---|---|---|---|
| `session:state:{session_id}` | String (JSON blob) | 5 min, refreshed on write | **Rust** | `SessionState` hot cache |
| `session:lock:{session_id}` | String (lock token) | 10 s | **Rust** | Optimistic locking during turn processing |
| `budget:session:{session_id}` | String (float) | session lifetime | **Python** | Per-session LLM spend accumulator |
| `budget:project:{project_id}` | String (float) | 30 days | **Python** | Per-project LLM spend accumulator |
| `ratelimit:{tenant_id}:{window}` | String (counter) | 60 s window | **Go** | API rate limiting per tenant |
| `idempotency:{request_id}` | String (response hash) | 24 h | **Go** | Idempotency keys for upload requests |
| `events:upload:complete` | Pub/Sub channel | — | Publisher: Python | Notifies Rust when ingestion finishes |
| `events:budget:threshold` | Pub/Sub channel | — | Publisher: Rust | Notifies Go when budget limit approaches |
| `events:signoff:received` | Pub/Sub channel | — | Publisher: Go | Notifies Rust when sign-off token is burned |

### 2.3 Session State Cache Pattern

The Rust state machine uses a write-through cache:

```
READ (every turn):
  1. GET session:state:{session_id}
  2. Cache HIT  → deserialize and use
     Cache MISS → SELECT from PostgreSQL, SET in Redis with 5-min TTL

WRITE (after every successful turn):
  1. Write updated SessionState to PostgreSQL (atomic)
  2. SET session:state:{session_id} {serialized_state} EX 300
```

The PostgreSQL write always precedes the Redis write. If the Redis write fails, the session falls back to PostgreSQL on the next read — no data is lost. If the PostgreSQL write fails, the Redis key is not updated and the session state remains consistent.

The 5-minute TTL means a session idle for more than 5 minutes will incur one PostgreSQL read on resumption. This is intentional — stale cache entries that survive a service restart should expire rather than serving outdated state.

### 2.4 Budget Tracking Pattern

The `BudgetTracker` in the Python service tracks spend using atomic Redis operations:

```python
# After each LLM call completes
await redis.incrbyfloat(f"budget:session:{session_id}", cost_usd)
await redis.incrbyfloat(f"budget:project:{project_id}", cost_usd)

# Check before dispatching a premium-tier call
session_spent = float(await redis.get(f"budget:session:{session_id}") or 0.0)
if session_spent >= SESSION_BUDGET_LIMIT_USD:  # 5.00
    # degrade to fallback model
```

`INCRBYFLOAT` is atomic in Redis — concurrent calls from multiple async tasks in the Python service will not produce race conditions on the budget counter. The PostgreSQL `llm_call_log` is the authoritative record; Redis is the fast guard.

### 2.5 Pub/Sub Event Pattern

Services communicate asynchronous state changes through Redis pub/sub channels. The canonical flow for document ingestion:

```
1. Python completes ingestion and indexing
2. Python publishes:
   PUBLISH events:upload:complete
     {"session_id": "...", "document_id": "...", "checkpoint": "B", "tenant_id": "..."}

3. Rust subscriber receives the event
4. Rust calls its own NotifyUploadComplete handler (same logic as the gRPC RPC)
5. If a hard gate is now resolved, Rust updates SessionState in PostgreSQL + Redis
```

These channels are not durable. A Rust instance that restarts between step 2 and step 5 will miss the event. The Go service compensates by calling `StateEngine.NotifyUploadComplete` via gRPC directly after a successful S3 upload — the pub/sub channel is a secondary notification path, not the primary one.

---

## 3. Object Storage — S3

### 3.1 Purpose

S3 stores two categories of binary objects:

1. **Raw uploaded documents** — the original files uploaded by the BA. These are ingested and indexed, but the raw bytes are kept for re-ingestion, version tracking, and audit.
2. **Export artifacts** — BRDs, HLDs, and specification exports generated by the Python service. Served to clients via pre-signed URLs.

S3 is not queried by the Rust state machine or the Python AI pipeline at runtime — it is a write-once ingest target and a read-once export source. All runtime retrieval uses PostgreSQL (embeddings and structured data).

### 3.2 Path Convention

All paths are tenant-scoped at the prefix level. No cross-tenant prefix access is possible.

```
{tenant_id}/
  {project_id}/
    raw/
      {document_id}/{original_filename}      ← uploaded source files
    exports/
      {artifact_id}/{artifact_type}.{ext}    ← BRDs, HLDs, spec exports
    sign-off/
      {sign_off_id}/sign_off_copy.pdf        ← the specific artifact sent for client sign-off
```

Examples:
```
3fa85f64-5717-4562-b3fc-2c963f66afa6/
  c56a4180-65aa-42ec-a945-5fd21dec0538/
    raw/
      d290f1ee-6c54-4b01-90e6-d701748f0851/Requirements_Brief_v2.pdf
    exports/
      a1b2c3d4-e5f6-7890-abcd-ef1234567890/brd.docx
      a1b2c3d4-e5f6-7890-abcd-ef1234567890/brd.pdf
    sign-off/
      7f3d5c2e-1a4b-8e9f-2c6d-0a1b2c3d4e5f/sign_off_copy.pdf
```

### 3.3 Access Pattern

The Go API gateway handles all S3 interactions with the client:

- **Upload**: Go receives the multipart upload, streams it to S3 at the `raw/` path, then calls `Python.IngestDocument` with the S3 URI. The BA never receives a presigned upload URL — the gateway is the intermediary.
- **Download (export)**: Go generates a short-lived presigned `GET` URL (15-minute expiry) and returns it to the client. The client fetches directly from S3. Go never proxies the file content.
- **Sign-off copy**: When a `ClientSignOff` record transitions to `signed`, Go generates a presigned URL with a 7-day expiry for the stakeholder's review link.

The Python service writes to S3 (for exports and sign-off copies) using `boto3`. It never generates presigned URLs — that is Go's responsibility.

---

## 4. Multi-Tenancy Strategy

Tenant isolation is enforced at three independent layers. Bypassing any one layer alone is not sufficient to access another tenant's data.

| Layer | Mechanism | Enforced By |
|---|---|---|
| **Application** | JWT claim `tenant_id` validated on every request | Go API Gateway |
| **Database** | RLS policy `tenant_id = current_setting('app.current_tenant_id')` on all tenant tables | PostgreSQL |
| **Vector retrieval** | `tenant_id` filter is a mandatory WHERE clause in every chunk query | Python RAG node |
| **Object storage** | S3 path prefix `{tenant_id}/` enforced by Go before any presigned URL generation | Go API Gateway |

The vector retrieval filter is listed explicitly because RLS does not apply to pgvector ANN queries by default — the `WHERE` clause with `tenant_id` must be included in the query by the application. The mandatory filter list in `ontology.md` Section 4 is enforced in code by the `RAGRetrievalNode`, which is tested to reject queries without these filters at startup.

---

## 5. Data Flow by Operation

### 5.1 Document Ingestion

```
BA uploads file
  → Go: stream to S3 at {tenant_id}/{project_id}/raw/{document_id}/
  → Go: INSERT into document (status = 'processing')
  → Go: call Python.IngestDocument(s3_uri, document_id, session_id)
  → Python: parse file (pypdf / python-docx / openpyxl)
  → Python: PII scrub (presidio-analyzer)
  → Python: semantic chunking → N chunks
  → Python: batch embed with voyage-large-2 (up to 128 chunks per API call)
  → Python: INSERT into chunk (embedding, sparse_vector, metadata)
  → Python: UPDATE document SET status = 'indexed'
  → Python: PUBLISH events:upload:complete → Redis
  → Go: call Rust.NotifyUploadComplete(session_id, document_id, checkpoint)
  → Rust: re-evaluate upload AC → may resolve hard gate
  → Rust: UPDATE session SET state = ... (PostgreSQL + Redis cache)
```

### 5.2 Per-Turn RAG Retrieval

```
BA sends message
  → Rust: GET session:state:{session_id} (Redis cache-first)
  → Rust: (gate + AC evaluation — PostgreSQL not needed)
  → Rust: call Python.RunPipeline(session_state, message)
  → Python: embed query with voyage-large-2
  → Python: BM25 candidate retrieval (rank-bm25, in-memory)
  → Python: hybrid SQL query (PostgreSQL: dense + sparse, mandatory filters)
  → Python: cross-encoder re-rank (top-k results)
  → Python: INCRBYFLOAT budget:session:{session_id} (Redis, after LLM call)
  → Python: INSERT into llm_call_log (PostgreSQL, after LLM call)
  → Python: stream tokens back to Rust
  → Rust: UPDATE session SET state = ... (PostgreSQL atomic write)
  → Rust: SET session:state:{session_id} (Redis write-through)
```

---

## 6. Operational Considerations

### 6.1 Migrations

Database schema changes are applied via numbered migration files in `services/state-machine/migrations/` (Rust, sqlx) and `services/ai-orchestration/migrations/` (Python, using `asyncpg` migration tooling). Migrations are:

- **Additive only** in production: add columns with defaults, add tables, add indexes. Never drop or rename in the same migration that adds.
- **Reviewed against the RLS invariant**: every new table with `tenant_id` must have the RLS policy applied in the same migration.
- **Applied in CI before tests run**: the test suite runs against a real PostgreSQL instance with migrations applied. No test hits a mocked database.

### 6.2 pgvector Index Maintenance

The HNSW index on `chunk.embedding` is maintained automatically on insert. Two operational triggers to be aware of:

- **After bulk re-embedding** (e.g., model upgrade to a new embedding dimension): `REINDEX INDEX CONCURRENTLY idx_chunk_embedding_hnsw` after the new embeddings are in place. This runs online without locking reads.
- **After tombstoning large numbers of chunks**: run `VACUUM chunk` to reclaim space and let the index planner see the reduced live row count.

### 6.3 Redis Eviction Policy

Redis must be configured with `maxmemory-policy = allkeys-lru`. This ensures that if Redis approaches its memory limit, it evicts the least-recently-used keys first — which will be stale session caches, not the active budget counters. Budget counters are touched on every LLM call and will be retained under normal load.

### 6.4 S3 Retention and WORM

For workspaces with `compliance_flags` containing `HIPAA` or `SOC2`, the `raw/` prefix must be stored in an S3 bucket with Object Lock enabled in Compliance mode. The retention period defaults to `workspace.retention_days` (default: 90 days). The `sign-off/` prefix retains indefinitely for all workspaces — these are legal records and are never deleted.

---

## 7. What This Document Does Not Decide

The following decisions remain open in `docs/sprints/sprint0/DECISIONS.md` and are not resolved by this strategy:

| Decision | Status | Impact on this document |
|---|---|---|
| **D-005** — Single PostgreSQL vs. split vector DB | OPEN | This document assumes single PostgreSQL + pgvector. If a dedicated vector store is chosen, Section 1 splits into two separate strategies. |
| **D-006** — Redis managed service selection | OPEN | The Redis strategy (Section 2) applies identically to Upstash, ElastiCache, or self-hosted Redis 7. The selection affects ops config only. |
| **D-007** — Object storage provider | OPEN | Section 3 uses S3 API semantics. Cloudflare R2 and GCP Cloud Storage are S3-compatible — the path conventions and access patterns do not change. |

---

> Database Strategy · Chitragupt · Sprint 1 · May 2026
