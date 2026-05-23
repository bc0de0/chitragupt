-- 0002: Documents table — owned by Python service
-- Tracks every file uploaded to a project with its ingestion lifecycle.

CREATE TABLE IF NOT EXISTS documents (
    document_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID        NOT NULL,
    project_id      UUID        NOT NULL,
    session_id      UUID,
    filename        TEXT        NOT NULL,
    source_type     TEXT        NOT NULL DEFAULT 'pdf',
    file_hash       TEXT        NOT NULL,
    r2_key          TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'indexed', 'failed', 'tombstoned')),
    trust_tier      INTEGER     NOT NULL DEFAULT 3
                    CHECK (trust_tier BETWEEN 1 AND 5),
    token_count     INTEGER,
    error_message   TEXT,
    is_superseded   BOOLEAN     NOT NULL DEFAULT FALSE,
    superseded_by   UUID        REFERENCES documents(document_id),
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (file_hash, project_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_project  ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_documents_status   ON documents(status);
