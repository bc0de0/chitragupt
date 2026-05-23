-- 0005: hybrid_search() SQL function
-- Called by RAGRetrievalNode for every per-turn retrieval.
-- Combines pgvector cosine similarity (dense) with BM25 weights (sparse).
-- Returns top_k results ordered by weighted hybrid score.
--
-- Parameters:
--   query_embedding  - voyage-large-2 embedding of the user query (vector(1536))
--   bm25_tokens      - BM25 term weights computed in Python: {"term": weight}
--   p_workspace_id   - mandatory tenant isolation filter
--   p_project_id     - mandatory session scope filter
--   dense_w          - weight for dense score (default 0.7)
--   sparse_w         - weight for sparse BM25 score (default 0.3)
--   top_k            - number of results to return (default 20)

CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding  vector(1536),
    bm25_tokens      jsonb,
    p_workspace_id   uuid,
    p_project_id     uuid,
    dense_w          float DEFAULT 0.7,
    sparse_w         float DEFAULT 0.3,
    top_k            int   DEFAULT 20
)
RETURNS TABLE (
    chunk_id        uuid,
    document_id     uuid,
    content         text,
    section_title   text,
    page_number     integer,
    trust_tier      integer,
    source_type     text,
    score           float
)
LANGUAGE plpgsql
AS $$
DECLARE
    candidate_ids uuid[];
BEGIN
    -- Step 1: ANN dense retrieval — get top-50 candidates by cosine similarity
    SELECT ARRAY(
        SELECT dc.chunk_id
        FROM document_chunks dc
        WHERE dc.workspace_id = p_workspace_id
          AND dc.project_id   = p_project_id
          AND dc.is_active    = TRUE
          AND (dc.valid_until IS NULL OR dc.valid_until > now())
        ORDER BY dc.embedding <=> query_embedding
        LIMIT 50
    ) INTO candidate_ids;

    -- Step 2: Hybrid scoring — dense cosine + BM25 sparse, return top_k
    RETURN QUERY
    SELECT
        dc.chunk_id,
        dc.document_id,
        dc.content,
        dc.section_title,
        dc.page_number,
        dc.trust_tier,
        dc.source_type,
        (
            dense_w  * (1.0 - (dc.embedding <=> query_embedding))
            + sparse_w * COALESCE(
                (
                    SELECT SUM((bm25_tokens ->> key)::float * (dc.sparse_vector ->> key)::float)
                    FROM jsonb_object_keys(bm25_tokens) AS t(key)
                    WHERE dc.sparse_vector ? key
                ),
                0.0
            )
        )::float AS score
    FROM document_chunks dc
    WHERE dc.chunk_id  = ANY(candidate_ids)
      AND dc.workspace_id = p_workspace_id
      AND dc.project_id   = p_project_id
      AND dc.is_active    = TRUE
    ORDER BY score DESC
    LIMIT top_k;
END;
$$;
