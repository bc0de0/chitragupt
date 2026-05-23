-- Migration 002: Document storage and vector chunk table
-- Implements the vector storage layer defined in docs/sprints/sprint0/DATABASE.md
-- Requires Migration 001 (workspaces, projects, sessions) to run first.
-- Requires pgvector extension. Embedding dimension: 1024 (voyage-large-2).

-- ============================================================
-- Extension
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- documents
-- Metadata record for every file uploaded to a session.
-- Raw file bytes live in Cloudflare R2; this table tracks ingestion state.
-- ============================================================

CREATE TABLE documents (
  document_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  project_id            UUID        NOT NULL REFERENCES projects(project_id),
  workspace_id          UUID        NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  original_filename     TEXT        NOT NULL,
  source_type           TEXT        NOT NULL DEFAULT 'pdf',   -- pdf | docx | image | txt | url
  document_type         TEXT,                                  -- org_chart | scope_doc | brd | wireframe | policy | other
  trust_tier            SMALLINT    NOT NULL DEFAULT 3,        -- 1 (primary) – 5 (low)
  status                TEXT        NOT NULL DEFAULT 'pending', -- pending | ingesting | indexed | failed
  file_hash             TEXT,       -- SHA-256, used for deduplication
  r2_key                TEXT,       -- storage path in R2
  page_count            INT,
  token_count           INT,
  is_superseded         BOOLEAN     NOT NULL DEFAULT FALSE,
  superseded_by         UUID        REFERENCES documents(document_id),
  ingested_at           TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX documents_session_idx   ON documents (session_id);
CREATE INDEX documents_project_idx   ON documents (project_id, workspace_id);
CREATE INDEX documents_status_idx    ON documents (workspace_id, status);
CREATE UNIQUE INDEX documents_hash_idx ON documents (workspace_id, project_id, file_hash)
  WHERE file_hash IS NOT NULL AND is_superseded = FALSE;

CREATE TRIGGER documents_updated_at
  BEFORE UPDATE ON documents
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_tenant_isolation ON documents
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- document_chunks
-- Chunked text from every indexed document.
-- embedding: 1024-dim vector from voyage-large-2
-- sparse_vector: BM25 token weights stored as JSONB {token: weight}
-- All RAG retrieval queries filter by workspace_id + project_id + is_active.
-- ============================================================

CREATE TABLE document_chunks (
  chunk_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id           UUID        NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
  workspace_id          UUID        NOT NULL,
  project_id            UUID        NOT NULL,
  content               TEXT        NOT NULL,
  embedding             vector(1024) NOT NULL,
  sparse_vector         JSONB       NOT NULL DEFAULT '{}',  -- {token: bm25_weight}
  chunk_index           INT         NOT NULL,               -- 0-based position in document
  token_count           INT         NOT NULL,
  section_title         TEXT,
  page_number           INT,
  is_active             BOOLEAN     NOT NULL DEFAULT TRUE,
  valid_from            TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_until           TIMESTAMPTZ,                        -- null = no expiry
  confidence_modifier   NUMERIC(3,2) NOT NULL DEFAULT 1.0, -- trust_tier influence
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW index for approximate nearest-neighbour search (cosine similarity)
-- m=16 ef_construction=64 are conservative defaults for MVP scale.
-- Tune upward (m=32, ef=128) if recall drops below 95% at 1M+ vectors.
CREATE INDEX document_chunks_embedding_idx ON document_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Partial index: only active, non-expired chunks participate in retrieval
CREATE INDEX document_chunks_active_idx ON document_chunks (workspace_id, project_id)
  WHERE is_active = TRUE AND (valid_until IS NULL OR valid_until > now());

-- GIN index on sparse_vector for BM25 token lookups
CREATE INDEX document_chunks_sparse_idx ON document_chunks USING gin (sparse_vector);

-- Covering index for tenant-scoped pagination
CREATE INDEX document_chunks_doc_order_idx ON document_chunks (document_id, chunk_index);

ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY document_chunks_tenant_isolation ON document_chunks
  USING (workspace_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- Retrieval helper: hybrid_search
-- Combines dense cosine similarity (pgvector) with sparse BM25 score.
-- Called from RAGRetrievalNode; weights match orchestration.yaml config.
-- Parameters:
--   query_embedding  — 1024-dim vector from voyage-large-2
--   bm25_tokens      — JSONB {token: query_weight} for sparse scoring
--   p_workspace_id   — tenant filter
--   p_project_id     — project filter
--   dense_weight     — 0.0–1.0, default 0.7 (from config)
--   sparse_weight    — 0.0–1.0, default 0.3 (from config)
--   top_k            — result limit before reranking, default 20
-- ============================================================

CREATE OR REPLACE FUNCTION hybrid_search(
  query_embedding  vector(1024),
  bm25_tokens      JSONB,
  p_workspace_id   UUID,
  p_project_id     UUID,
  dense_weight     NUMERIC DEFAULT 0.7,
  sparse_weight    NUMERIC DEFAULT 0.3,
  top_k            INT     DEFAULT 20
)
RETURNS TABLE (
  chunk_id        UUID,
  document_id     UUID,
  content         TEXT,
  section_title   TEXT,
  page_number     INT,
  hybrid_score    NUMERIC,
  dense_score     NUMERIC,
  sparse_score    NUMERIC,
  confidence_modifier NUMERIC
)
LANGUAGE sql STABLE AS $$
  WITH dense AS (
    SELECT
      dc.chunk_id,
      dc.document_id,
      dc.content,
      dc.section_title,
      dc.page_number,
      dc.confidence_modifier,
      1 - (dc.embedding <=> query_embedding) AS dense_score
    FROM document_chunks dc
    WHERE dc.workspace_id = p_workspace_id
      AND dc.project_id   = p_project_id
      AND dc.is_active    = TRUE
      AND (dc.valid_until IS NULL OR dc.valid_until > now())
    ORDER BY dc.embedding <=> query_embedding
    LIMIT top_k * 3   -- over-fetch for sparse re-scoring
  ),
  scored AS (
    SELECT
      d.chunk_id,
      d.document_id,
      d.content,
      d.section_title,
      d.page_number,
      d.confidence_modifier,
      d.dense_score,
      -- Sparse score: sum of query_weight * chunk_weight for matching tokens
      COALESCE(
        (
          SELECT SUM((bm25_tokens->>key)::NUMERIC * (dc2.sparse_vector->>key)::NUMERIC)
          FROM document_chunks dc2, jsonb_object_keys(bm25_tokens) AS key
          WHERE dc2.chunk_id = d.chunk_id
            AND dc2.sparse_vector ? key
        ),
        0
      ) AS sparse_score
    FROM dense d
  )
  SELECT
    s.chunk_id,
    s.document_id,
    s.content,
    s.section_title,
    s.page_number,
    (dense_weight * s.dense_score + sparse_weight * s.sparse_score) * s.confidence_modifier AS hybrid_score,
    s.dense_score,
    s.sparse_score,
    s.confidence_modifier
  FROM scored s
  ORDER BY hybrid_score DESC
  LIMIT top_k;
$$;

-- ============================================================
-- cost_log
-- Per-turn LLM cost record for auditing and budget enforcement.
-- ============================================================

CREATE TABLE cost_log (
  cost_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id            UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  workspace_id          UUID        NOT NULL,
  llm_feature           TEXT        NOT NULL,  -- matches LLMFeature enum
  model_id              TEXT        NOT NULL,
  input_tokens          INT         NOT NULL DEFAULT 0,
  output_tokens         INT         NOT NULL DEFAULT 0,
  cost_usd              NUMERIC(10,6) NOT NULL,
  budget_stage          TEXT        NOT NULL DEFAULT 'NORMAL', -- NORMAL | CAUTION | CRITICAL | EXHAUSTED
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX cost_log_session_idx   ON cost_log (session_id);
CREATE INDEX cost_log_workspace_idx ON cost_log (workspace_id, created_at DESC);

ALTER TABLE cost_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY cost_log_tenant_isolation ON cost_log
  USING (workspace_id = current_setting('app.tenant_id')::UUID);
