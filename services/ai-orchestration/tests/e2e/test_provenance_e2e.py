"""E2E Suite — Document Provenance.

T-E2E-05: Entity extracted from uploaded document carries source chunk IDs.

Requires: Full Docker Compose stack + OPENROUTER_API_KEY.
Run with: pytest -m e2e
"""
import pytest


@pytest.mark.e2e
@pytest.mark.skip(reason="Requires full Docker Compose stack + API keys. Run with: pytest -m e2e")
async def test_e2e_05_entity_from_document_has_source_chunk_ids():
    """
    T-E2E-05: After uploading a document that mentions a specific actor, the
    Entity extracted from that document must carry the source_chunk_ids pointing
    back to the originating document chunk.

    Acceptance criteria:
    1. Upload a test PDF containing a specific actor name
    2. Send a pipeline turn mentioning the same actor
    3. The extracted Entity for that actor must have non-empty source_chunk_ids
    4. Each chunk_id must correspond to an actual chunk in the document_chunks table

    Requires: Full stack + real LLM calls + PostgreSQL + pgvector.
    """
    raise NotImplementedError("E2E test — requires full Docker Compose stack.")
