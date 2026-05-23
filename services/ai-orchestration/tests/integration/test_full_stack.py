"""Domain 6 — Code Integration: Full gRPC Stack stub.

T-INT-11: Go HTTP POST → Rust state → Python pipeline → Go SSE complete.

Requires: Full Docker Compose stack (all services).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires full Docker Compose stack. Run with: pytest -m integration")
async def test_int_11_full_grpc_stack_http_to_sse_complete():
    """
    T-INT-11: A single POST /turn request must traverse the full stack:
    Go gateway → Rust state machine → Python pipeline → Go SSE stream.
    The final event must be 'complete' with a non-empty turn_result.
    """
    raise NotImplementedError("Integration test — requires full Docker Compose stack.")
