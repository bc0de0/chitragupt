"""Domain 6 — Code Integration: Go → Python gRPC Orchestration stubs.

T-INT-06: Go → Python RunPipeline streams ≥ 1 token before complete event.
T-INT-07: Go → Python IngestDocument returns accepted; background task fires.

Requires: Python gRPC servicer + Go gateway (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Python gRPC servicer + Go gateway. Run with: pytest -m integration")
async def test_int_06_run_pipeline_streams_tokens_before_complete():
    """
    T-INT-06: A RunPipeline gRPC call must yield at least one 'token' SSE event
    before the 'complete' event.
    """
    raise NotImplementedError("Integration test — requires Python gRPC servicer.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Python gRPC servicer + Go gateway. Run with: pytest -m integration")
async def test_int_07_ingest_document_returns_accepted_and_fires_background_task():
    """
    T-INT-07: IngestDocument must return an 'accepted' status immediately, and
    the background ingestion task must fire and update document status to 'indexed'.
    """
    raise NotImplementedError("Integration test — requires Python gRPC servicer.")
