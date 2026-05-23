"""Domain 2 & 6 — Edge Cases and Integration: Ingestion stubs.

T-EDGE-09: Duplicate document upload returns existing document_id (hash dedup).
T-INT-08: Python → asyncpg: chunks retrievable by hybrid_search within same session.
T-INT-09: Python → asyncpg: RLS enforced — session A cannot retrieve session B chunks.

Requires: PostgreSQL + pgvector + Python service (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires PostgreSQL + asyncpg. Run with: pytest -m integration")
async def test_edge_09_duplicate_document_upload_is_deduplicated():
    """
    T-EDGE-09: Uploading the same document bytes twice (same content hash) must
    return the existing document_id on the second call rather than creating a duplicate.
    """
    raise NotImplementedError("Integration test — requires PostgreSQL.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires PostgreSQL + pgvector. Run with: pytest -m integration")
async def test_int_08_inserted_chunks_retrievable_by_hybrid_search():
    """
    T-INT-08: After ingesting a document, its chunks must be retrievable via
    hybrid_search() within the same session's workspace scope.
    """
    raise NotImplementedError("Integration test — requires PostgreSQL + pgvector.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires PostgreSQL + pgvector with RLS. Run with: pytest -m integration")
async def test_int_09_rls_prevents_cross_session_chunk_retrieval():
    """
    T-INT-09: Chunks indexed under workspace A must not appear in hybrid_search()
    results for a query in workspace B (Row Level Security enforced).
    """
    raise NotImplementedError("Integration test — requires PostgreSQL with RLS.")
