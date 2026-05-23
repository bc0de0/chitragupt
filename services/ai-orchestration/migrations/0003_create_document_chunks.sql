-- 0003: Document chunks table — owned by Python service
-- Vector store: each chunk holds a voyage-large-2 embedding (dim=1536)
-- and a BM25 sparse_vector for hybrid retrieval.
-- NOTE: embedding dimension is locked to 1536 for this vector namespace.
-- Changing it requires a full re-embed migration (see DATABASE.md §1.11).

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID            NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    workspace_id        UUID            NOT NULL,
    project_id          UUID            NOT NULL,
    content             TEXT            NOT NULL,
    embedding           vector(1536)    NOT NULL,
    sparse_vector       JSONB,          -- BM25 term weights: {"term": weight, ...}
    chunk_index         INTEGER         NOT NULL,
    token_count         INTEGER         NOT NULL,
    section_title       TEXT,
    page_number         INTEGER,
    source_type         TEXT            NOT NULL DEFAULT 'pdf',
    trust_tier          INTEGER         NOT NULL DEFAULT 3
                        CHECK (trust_tier BETWEEN 1 AND 5),
    confidence_modifier FLOAT           NOT NULL DEFAULT 1.0,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    valid_from          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    valid_until         TIMESTAMPTZ,
    language            TEXT            NOT NULL DEFAULT 'en',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_document   ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_workspace  ON document_chunks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_chunks_project    ON document_chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_chunks_active     ON document_chunks(project_id, is_active)
    WHERE is_active = TRUE;
