# 03 — Data and Storage: PostgreSQL, pgvector, Redis, and Vector Search

**Why this matters for Chitragupt:** The system handles multiple distinct data types — structured session data, semantic document embeddings, active session cache, audit trails, and file storage. Each requires a different storage strategy. Getting this wrong means either paying too much, querying too slowly, or leaking data between tenants.

---

## 1. The Storage Strategy Map

Chitragupt routes data to different stores based on its characteristics:

| Data Type | Store | Why |
|---|---|---|
| Sessions, users, requirements, decisions | PostgreSQL | ACID transactions, relational queries, RLS |
| Document chunks + embeddings | PostgreSQL + pgvector | Semantic search co-located with metadata |
| Active session cache | Redis | Sub-millisecond reads, TTL-based expiry |
| File storage (PDFs, images, audio) | Cloudflare R2 | Low-cost object storage, CDN-friendly |
| Audit trail | PostgreSQL (append-only table) | Full history with point-in-time queries |
| Cost/usage telemetry | PostgreSQL | Aggregated per-tenant budget tracking |

---

## 2. PostgreSQL

PostgreSQL is a powerful open-source relational database. It is the backbone of Chitragupt's data layer because it supports ACID transactions, complex queries, Row Level Security, and — via the pgvector extension — vector search.

### Why PostgreSQL instead of a dedicated vector database?

Most vector databases (Pinecone, Weaviate, Qdrant) are excellent for pure vector search, but they lack:
- ACID transactions (critical for requirement state changes)
- Row Level Security (critical for multi-tenancy)
- Relational joins (requirements linked to sessions, sessions linked to tenants)

By using pgvector, Chitragupt gets vector search *and* relational data in one system — reducing operational complexity. Decision recorded in `docs/sprints/sprint0/DECISIONS.md`.

### Key concepts

**Tables:** Structured data storage with rows and columns. Every table in Chitragupt includes `tenant_id` and is protected by RLS.

**Transactions:** A group of operations that succeed or fail together. If inserting a requirement and updating the session state fails halfway through, PostgreSQL rolls back both.

**Indexes:** Structures that speed up queries. Without indexes, PostgreSQL scans every row. With indexes, it jumps directly to relevant rows.

**Migration:** A versioned SQL file that modifies the schema. Chitragupt rule: migrations are append-only — never modify a migration after it ships.

---

## 3. Row Level Security (RLS)

RLS is a PostgreSQL feature that enforces per-row access control at the database engine level — below the application layer.

### How it works

```sql
-- 1. Enable RLS on a table
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- 2. Create a policy — users only see rows matching their tenant_id
CREATE POLICY tenant_isolation ON sessions
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- 3. Application sets the tenant before every query
SET app.current_tenant_id = '550e8400-e29b-41d4-a716-446655440000';
SELECT * FROM sessions;
-- PostgreSQL automatically filters to only this tenant's sessions
```

### Why this matters

Even if there is a bug in application code that forgets to filter by `tenant_id`, RLS prevents data leakage. It is a defence-in-depth measure — security at the database layer, not just application layer.

**Chitragupt invariant:** Every table containing tenant-specific data has RLS enabled. No exceptions. This invariant is enforced in code review and CI.

### Propagating tenant_id through the stack

```
JWT arrives at Go gateway
  → middleware extracts tenant_id claim
  → passed via gRPC metadata to Rust / Python
  → set as app.current_tenant_id before every database connection
  → PostgreSQL enforces RLS automatically
```

---

## 4. pgvector

pgvector is a PostgreSQL extension that adds:
- A `vector` column type
- Vector similarity search operators (`<->` cosine, `<=>` L2, `<#>` inner product)
- HNSW and IVFFlat indexing for approximate nearest neighbour search

### Storing an embedding

```sql
CREATE TABLE document_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,
    document_id UUID NOT NULL REFERENCES documents(id),
    content     TEXT NOT NULL,
    embedding   vector(1536),    -- 1536 dimensions = voyage-large-2 output
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### The HNSW Index

HNSW (Hierarchical Navigable Small World) is a graph-based approximate nearest neighbour algorithm. It trades a small amount of recall accuracy for very fast query times.

```sql
-- Build HNSW index for cosine similarity search
CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Parameters explained:**
- `m = 16` — each node in the graph connects to 16 neighbours. Higher = better recall, more memory.
- `ef_construction = 64` — number of candidates considered during index build. Higher = better recall, slower build.
- `vector_cosine_ops` — use cosine distance as the similarity metric.

**HNSW vs IVFFlat:**

| | HNSW | IVFFlat |
|---|---|---|
| Query speed | Fast | Slower |
| Build speed | Slow | Fast |
| Memory | More | Less |
| Recall quality | Higher | Lower |
| Best for | Production queries | Prototyping |

Chitragupt uses HNSW — build once, query often.

---

## 5. Hybrid Search

Pure vector search (dense retrieval) finds semantically similar content. But sometimes the user asks for specific terms or IDs that semantic similarity misses. Hybrid search combines both:

```
Query: "What is the tenant isolation requirement?"
       ↓
Dense search (cosine similarity):  top-50 semantically similar chunks
BM25 sparse search (keyword):      top-50 chunks containing "tenant isolation"
       ↓
Reciprocal Rank Fusion (RRF):      merge and re-rank both lists
       ↓
Re-ranker model:                   top-20 final results
```

### Chitragupt hybrid weights

- **70% dense (cosine)** — semantic similarity
- **30% sparse (BM25)** — keyword relevance
- **Top-50** candidates from each, fused to top-50, then re-ranked to **top-20**

### Why not 100% dense?

Dense search sometimes misses exact matches when the embedding space compresses very similar concepts together. BM25 anchors keyword precision. The 70/30 split was determined empirically for BA domain content.

---

## 6. Redis

Redis is an in-memory data store — reads are measured in microseconds rather than milliseconds. Chitragupt uses Redis for:

### Active session state

```
Key:   session:{session_id}:state
Value: JSON blob with current phase, turn count, extracted entities
TTL:   1 hour (auto-expires inactive sessions)
```

BA sessions need sub-millisecond reads between turns. PostgreSQL is too slow for this hot path.

### Pub/sub event bus

```
Go gateway subscribes to channel: events:{session_id}
Python AI service publishes to:   events:{session_id}
Message: {"type": "turn_complete", "session_id": "...", "guidance": "..."}
```

When the AI pipeline finishes processing a turn, it publishes to Redis. The Go gateway is already subscribed and immediately pushes the result to the WebSocket.

### Redis key namespacing convention

```
session:{uuid}:state        — active session state
session:{uuid}:ttl          — session timeout management
budget:{tenant_id}:day      — daily budget accumulator
events:{session_id}         — pub/sub channel per session
rate:{tenant_id}:{endpoint} — rate limiter counter
```

---

## 7. Migration Strategy

Chitragupt's rules for schema migrations:

1. **Append-only:** Never modify a migration file after it is merged to main
2. **One change per file:** A migration that does two unrelated things is harder to roll back
3. **Backward-compatible changes:** Add columns as nullable before making them required
4. **Never rename:** Add the new column, migrate data, deprecate old — in three separate migrations
5. **Test against production-size data:** A migration that takes 10s on 1,000 rows may take 2 hours on 10M rows

---

## 8. Resources

### Official Documentation

| Resource | URL | What to read |
|---|---|---|
| PostgreSQL 18 docs | [postgresql.org/docs/current/](https://www.postgresql.org/docs/current/) | Row Level Security, indexes, EXPLAIN |
| pgvector GitHub | [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) | Installation, index types, distance operators, language clients |
| Redis docs | [redis.io/docs/latest/](https://redis.io/docs/latest/) | Data structures, pub/sub, TTL, client libraries |
| pgvector Python client | [github.com/pgvector/pgvector-python](https://github.com/pgvector/pgvector-python) | How to store and query vectors from Python |

### Deep Dives

| Resource | What you will learn |
|---|---|
| [HNSW paper (Malkov & Yashunin)](https://arxiv.org/abs/1603.09320) | How the HNSW graph structure enables fast approximate search |
| [BM25 explained (Robertson & Zaragoza)](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf) | The math behind sparse keyword retrieval |
| [Reciprocal Rank Fusion (Cormack et al.)](https://dl.acm.org/doi/10.1145/1571941.1572114) | How to fuse dense and sparse results |
| [PostgreSQL RLS tutorial](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) | Official RLS docs with examples |
| [Redis pub/sub docs](https://redis.io/docs/latest/develop/interact/pubsub/) | How the Go↔Python event channel works |

### Key questions to ask yourself when designing storage

1. Does this data need ACID transactions? → PostgreSQL
2. Is this data read thousands of times per second? → Redis first
3. Does this data need semantic search? → pgvector
4. Is this a large binary file? → Object storage (R2)
5. Does different data belong to different tenants? → RLS required

---

> Chitragupt Learning Hub · 03 Data and Storage · v0.1 · May 2026
