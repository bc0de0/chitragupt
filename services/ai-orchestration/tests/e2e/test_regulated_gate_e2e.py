"""E2E Suite — Regulated Domain Gate.

T-E2E-03: Document required before Phase 3→4 transition.

Requires: Full Docker Compose stack + OPENROUTER_API_KEY.
Run with: pytest -m e2e
"""
import pytest


@pytest.mark.e2e
@pytest.mark.skip(reason="Requires full Docker Compose stack + API keys. Run with: pytest -m e2e")
async def test_e2e_03_regulated_domain_requires_document_for_phase_3_to_4():
    """
    T-E2E-03: In a regulated-domain session (regulatory_context set), the Phase 3→4
    transition must be blocked until at least one document is uploaded and indexed.

    Acceptance criteria:
    1. Attempt Phase 3→4 without document upload → transition rejected, gap returned
    2. Upload and ingest a test PDF
    3. Attempt Phase 3→4 again → transition approved

    Requires: Full stack + real LLM calls + ingestion pipeline.
    """
    raise NotImplementedError("E2E test — requires full Docker Compose stack.")
