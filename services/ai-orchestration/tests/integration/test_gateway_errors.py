"""Domain 2 — Edge Cases: Go API Gateway Error Handling stubs.

T-EDGE-13: Non-existent session → 404 JSON.
T-EDGE-14: Rust gRPC unreachable → 503 within 6 s.
T-EDGE-15: Python gRPC unreachable → 503 within 6 s.

Requires: Running Go API gateway (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires running Go API gateway. Run with: pytest -m integration")
async def test_edge_13_nonexistent_session_returns_404():
    """
    T-EDGE-13: A POST /turn with a session_id that does not exist in the Rust state
    machine must return HTTP 404 with a JSON error body.
    """
    raise NotImplementedError("Integration test — requires running Go API gateway.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Go gateway with Rust service stopped. Run with: pytest -m integration")
async def test_edge_14_rust_grpc_unreachable_returns_503_within_6s():
    """
    T-EDGE-14: When the Rust gRPC service is stopped, the Go gateway must return
    HTTP 503 within 6 seconds (circuit-breaker or connection timeout).
    """
    raise NotImplementedError("Integration test — requires Go gateway + Rust service down.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Go gateway with Python service stopped. Run with: pytest -m integration")
async def test_edge_15_python_grpc_unreachable_returns_503_within_6s():
    """
    T-EDGE-15: When the Python gRPC service is stopped, the Go gateway must return
    HTTP 503 within 6 seconds.
    """
    raise NotImplementedError("Integration test — requires Go gateway + Python service down.")
